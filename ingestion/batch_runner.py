import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from llm.rate_limiter import extraction_semaphore
from ingestion.extractor_shared import extract_entities_from_batch
from schemas.entities import ExtractionResult
from config import MAX_EXTRACTION_WORKERS, EXTRACTION_CACHE_DIR


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


def _run_batch_guarded(batch: list[str], batch_num: int, total: int):
    cached = _load_cached(batch)
    if cached is not None:
        print(f"[batch_runner] Batch {batch_num}/{total} loaded from cache ({len(cached.entities)} entities).")
        return batch_num, cached, None

    with extraction_semaphore:
        try:
            result = extract_entities_from_batch(batch)
            _save_cached(batch, result)
            print(f"[batch_runner] Batch {batch_num}/{total} done ({len(result.entities)} entities).")
            return batch_num, result, None
        except Exception as e:
            print(f"[batch_runner] Batch {batch_num}/{total} FAILED: {e}")
            return batch_num, None, str(e)


def run_batches_parallel(batches: list[list[str]]) -> tuple[list[ExtractionResult], list[dict]]:
    total = len(batches)
    results, failures = [], []

    with ThreadPoolExecutor(max_workers=MAX_EXTRACTION_WORKERS) as executor:
        futures = {
            executor.submit(_run_batch_guarded, batch, i + 1, total): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            batch_index = futures[future]
            _, result, error = future.result()
            if result is not None:
                results.append(result)
            else:
                failures.append({"batch_index": batch_index, "batch": batches[batch_index], "error": error})

    print(f"[batch_runner] {len(results)}/{total} batches succeeded, {len(failures)} failed.")
    return results, failures


def retry_failed_batches(failures: list[dict], max_retries: int = 1):
    if not failures or max_retries <= 0:
        return [], failures
    print(f"[batch_runner] Retrying {len(failures)} failed batch(es)...")
    return run_batches_parallel([f["batch"] for f in failures])