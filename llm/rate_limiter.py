import threading

class ProviderSemaphore:
    """Bounds concurrent in-flight LLM calls. Not a token-bucket rate limiter —
    just caps concurrency, which is what actually matters for parallel batch
    extraction hammering a provider with a low OTPM limit."""
    def __init__(self, max_concurrent: int):
        self._semaphore = threading.Semaphore(max_concurrent)

    def __enter__(self):
        self._semaphore.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._semaphore.release()


from config import MAX_EXTRACTION_WORKERS
extraction_semaphore = ProviderSemaphore(MAX_EXTRACTION_WORKERS)    