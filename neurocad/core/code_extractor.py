"""Extract Python code from LLM responses (e.g., fenced blocks)."""

import re


def extract_code(raw: str) -> str:
    """Strip Markdown fenced code blocks and return clean Python code.

    Args:
        raw: Raw LLM response, possibly containing ```python ... ``` blocks.

    Returns:
        Extracted Python code (without fences). If no fences, returns raw text stripped.
    """
    if not raw:
        return ""

    # Pattern matches ```python ... ``` or ``` ... ``` (optional language)
    # DOTALL to match across newlines, MULTILINE to treat ^/$ per line.
    # The closing fence must be at start of line (with optional whitespace).
    pattern = r"^```(?:python)?\s*$\n?(.*?)^```\s*$"
    matches = re.findall(pattern, raw, flags=re.DOTALL | re.MULTILINE)
    if matches:
        # Concatenate all matches (multiple blocks)
        extracted = "\n".join(match.strip() for match in matches)
        return extracted.strip()

    # No fenced block found, return raw text stripped
    return raw.strip()
