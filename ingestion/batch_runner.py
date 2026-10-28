import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from llm.rate_limiter import extraction_semaphore
from ingestion.extractor_shared import extract_entities_from_batch
from schemas.entities import ExtractionResult
from config import MAX_EXTRACTION_WORKERS, EXTRACTION_CACHE_DIR


ProgressCallback = Callable[[dict], None]


def _cache_path(batch: list[str]) -> str:
    key = hashlib.sha256("\n".join(batch).encode()).hexdigest()[:24]
    return os.path.join(EXTRACTION_CACHE_DIR, f"{key}.json")


def _load_cached(batch: list[str]) -> ExtractionResult | None:
    path = _cache_path(batch)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return ExtractionResult.model_validate_json(f.read())
    except Exception:
        return None  # corrupt cache file -> just recompute


def _save_cached(batch: list[str], result: ExtractionResult):
    os.makedirs(EXTRACTION_CACHE_DIR, exist_ok=True)
    with open(_cache_path(batch), "w") as f:
        f.write(result.model_dump_json())


def _emit(on_progress: ProgressCallback | None, payload: dict) -> None:
    """Progress reporting must never be able to break ingestion."""
    if on_progress is None:
        return
    try:
        on_progress(payload)
    except Exception:
        pass


def _run_batch_guarded(
    batch: list[str],
    batch_num: int,
    total: int,
    on_progress: ProgressCallback | None = None,
):
    cached = _load_cached(batch)
    if cached is not None:
        print(f"[batch_runner] Batch {batch_num}/{total} loaded from cache ({len(cached.entities)} entities).")
        _emit(on_progress, {
            "event": "batch", "index": batch_num, "total": total,
            "status": "cached", "entities": len(cached.entities), "cached": True,
        })
        return batch_num, cached, None

    with extraction_semaphore:
        try:
            result = extract_entities_from_batch(batch)
            _save_cached(batch, result)
            print(f"[batch_runner] Batch {batch_num}/{total} done ({len(result.entities)} entities).")
            _emit(on_progress, {
                "event": "batch", "index": batch_num, "total": total,
                "status": "completed", "entities": len(result.entities), "cached": False,
            })
            return batch_num, result, None
        except Exception as e:
            print(f"[batch_runner] Batch {batch_num}/{total} FAILED: {e}")
            _emit(on_progress, {
                "event": "batch", "index": batch_num, "total": total,
                "status": "failed", "entities": None, "cached": False,
                # Only the exception type is exposed to the browser.
                "error": type(e).__name__,
            })
            return batch_num, None, str(e)


def run_batches_parallel(
    batches: list[list[str]],
    on_progress: ProgressCallback | None = None,
    batch_numbers: list[int] | None = None,
    total: int | None = None,
) -> tuple[list[ExtractionResult], list[dict]]:
    """Run batches concurrently.

    ``batch_numbers`` keeps the original 1-based batch number when retrying a
    subset of failed batches, so the UI can update the same batch tile instead
    of creating a second, misleading set.
    """

    total = total if total is not None else len(batches)
    numbers = batch_numbers or list(range(1, len(batches) + 1))
    results, failures = [], []

    with ThreadPoolExecutor(max_workers=MAX_EXTRACTION_WORKERS) as executor:
        futures = {}
        for i, batch in enumerate(batches):
            _emit(on_progress, {
                "event": "batch", "index": numbers[i], "total": total,
                "status": "running", "entities": None, "cached": False,
            })
            futures[executor.submit(_run_batch_guarded, batch, numbers[i], total, on_progress)] = i

        for future in as_completed(futures):
            subset_index = futures[future]
            _, result, error = future.result()
            if result is not None:
                results.append(result)
            else:
                failures.append({
                    "batch_index": numbers[subset_index] - 1,
                    "batch": batches[subset_index],
                    "error": error,
                })

    print(f"[batch_runner] {len(results)}/{len(batches)} batches succeeded, {len(failures)} failed.")
    return results, failures


def retry_failed_batches(
    failures: list[dict],
    max_retries: int = 1,
    on_progress: ProgressCallback | None = None,
    total: int | None = None,
):
    if not failures or max_retries <= 0:
        return [], failures
    print(f"[batch_runner] Retrying {len(failures)} failed batch(es)...")
    return run_batches_parallel(
        [f["batch"] for f in failures],
        on_progress=on_progress,
        batch_numbers=[f["batch_index"] + 1 for f in failures],
        total=total,
    )
