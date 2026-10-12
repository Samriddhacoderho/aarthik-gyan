import re

_THINK_BLOCK = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)
_THINK_UNCLOSED = re.compile(r"<think>.*\Z", flags=re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    """Removes Qwen-style <think>...</think> reasoning, including a cut-off one."""
    text = _THINK_BLOCK.sub("", text or "")
    text = _THINK_UNCLOSED.sub("", text)
    return text.strip()