from concurrent.futures import ThreadPoolExecutor, as_completed
from llm.rate_limiter import extraction_semaphore
from ingestion.extractor import extract_entities_from_batch
from schemas.entities import ExtractionResult
from config import MAX_EXTRACTION_WORKERS


def _run_batch_guarded(batch: list[str], batch_num: int, total: int) -> tuple[int, ExtractionResult | None, str | None]:
    """Runs one batch under the concurrency guard. Returns (batch_num, result, error)
    — result is None if it failed, error is None if it succeeded."""
    with extraction_semaphore:
        try:
            result = extract_entities_from_batch(batch)
            print(f"[batch_runner] Batch {batch_num}/{total} done ({len(result.entities)} entities).")
            return batch_num, result, None
        except Exception as e:
            print(f"[batch_runner] Batch {batch_num}/{total} FAILED: {e}")
            return batch_num, None, str(e)


def run_batches_parallel(batches: list[list[str]]) -> tuple[list[ExtractionResult], list[dict]]:
    """Runs all batches concurrently (bounded by MAX_EXTRACTION_WORKERS / the
    semaphore). Returns (successful_results, failed_batches) — failed_batches
    carries enough info to retry later without re-running everything."""
    total = len(batches)
    results = []
    failures = []

    with ThreadPoolExecutor(max_workers=MAX_EXTRACTION_WORKERS) as executor:
        futures = {
            executor.submit(_run_batch_guarded, batch, i + 1, total): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            batch_index = futures[future]
            batch_num, result, error = future.result()
            if result is not None:
                results.append(result)
            else:
                failures.append({"batch_index": batch_index, "batch": batches[batch_index], "error": error})

    print(f"[batch_runner] {len(results)}/{total} batches succeeded, {len(failures)} failed.")
    return results, failures


def retry_failed_batches(failures: list[dict], max_retries: int = 1) -> tuple[list[ExtractionResult], list[dict]]:
    """One retry pass over failed batches only — not the whole document.
    Cheap insurance for transient rate-limit failures that the tenacity retry
    inside extract_entities_from_batch already gave up on."""
    if not failures or max_retries <= 0:
        return [], failures

    print(f"[batch_runner] Retrying {len(failures)} failed batch(es)...")
    retry_batches = [f["batch"] for f in failures]
    results, still_failing = run_batches_parallel(retry_batches)
    return results, still_failing