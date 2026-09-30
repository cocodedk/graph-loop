"""ANSI colour for the live screen: the eight basic colours, bold and dim. Text is padded plain and
painted after, so with the codes removed the screen is the one without colour."""

from __future__ import annotations

CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "magenta": "35", "cyan": "36"}


def paint(text: str, style: str, on: bool = True) -> str:
    """`text` in `style` (a key of CODES); unchanged when `on` is false, `style` is empty or there is no text."""
    return f"\033[{CODES[style]}m{text}\033[0m" if on and style and text else text


def quiet(seconds: int) -> str:
    """The style of a step with no sign of life for `seconds`: yellow from 5 minutes, red from 15."""
    return "red" if seconds >= 900 else "yellow" if seconds >= 300 else ""


def costly(spent: float) -> str:
    """The style of a spec's cost, judged as it is, not as rounded: yellow above $3.99, red above $8."""
    return "red" if spent > 8 else "yellow" if spent > 3.99 else ""
