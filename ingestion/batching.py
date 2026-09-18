def estimate_tokens(text: str) -> int:
    """Rough estimate: 4 characters per token. Good enough for staying under a context window with margin."""
    return len(text) // 4


def batch_chunks(chunks: list[str], max_tokens_per_batch: int = 20000, max_chunks_per_batch: int = 15) -> list[list[str]]:
    """Groups chunk texts into batches bounded by BOTH an estimated token budget
    AND a max chunk count (extraction quality tends to degrade if you cram in
    too many chunks even when they'd technically fit token-wise).

    Returns a list of batches, where each batch is a list of chunk strings
    to be concatenated (with separators) into a single LLM call.
    """
    if not chunks:
        return []

    batches = []
    current_batch = []
    current_tokens = 0

    for chunk in chunks:
        chunk_tokens = estimate_tokens(chunk)

        would_exceed_tokens = current_tokens + chunk_tokens > max_tokens_per_batch
        would_exceed_count = len(current_batch) >= max_chunks_per_batch

        if current_batch and (would_exceed_tokens or would_exceed_count):
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(chunk)
        current_tokens += chunk_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def format_batch_for_prompt(batch: list[str]) -> str:
    """Joins a batch's chunks with clear delimiters so the LLM can tell
    where one chunk ends and the next begins — matters for not blending
    context across unrelated sections."""
    parts = []
    for i, chunk in enumerate(batch, 1):
        parts.append(f"--- CHUNK {i} ---\n{chunk}")
    return "\n\n".join(parts)