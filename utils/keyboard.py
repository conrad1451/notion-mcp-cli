# utils/keyboard.py
"""Cross-platform raw keyboard input handler for terminal applications.

Provides a unified interface for capturing raw keyboard input including arrow keys
and special characters on both Windows (using msvcrt) and Unix-like systems (using
tty/termios). Normalizes escape sequences to common key names like 'left', 'right',
'home', and 'end'.
"""

import sys
import os

if os.name == "nt":
    import msvcrt  # pylint: disable=import-error
else:
    import tty  # pylint: disable=import-error
    import termios  # pylint: disable=import-error


def get_key_input() -> str:
    """
    Cross-platform handler to capture raw keyboard input, including escape sequences.

    Returns:
        str: A normalized string representing the key (e.g., 'left', 'q', 'd').
    """
    # import sys
    # import os

    if os.name == "nt":  # Windows
        # import msvcrt
        key = msvcrt.getch()
        if key == b"\xe0":  # Special key prefix
            key = msvcrt.getch()
            special_keys = {b"M": "left", b"P": "right", b"G": "home", b"O": "end"}
            return special_keys.get(key, key.decode("utf-8", errors="ignore").lower())
        return key.decode("utf-8", errors="ignore").lower()
    # macOS and Linux
    # import tty
    # import termios

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(
        fd
    )  # pylint: disable=possibly-used-before-assignment
    try:
        tty.setraw(fd)  # pylint: disable=possibly-used-before-assignment
        key = sys.stdin.read(1)

        # Handle escape sequences for arrow keys
        if key == "\x1b":
            next_char = sys.stdin.read(1)
            if next_char == "[":
                arrow = sys.stdin.read(1)
                arrows = {"A": "up", "B": "down", "C": "right", "D": "left"}
                return arrows.get(arrow, arrow.lower())

        return key.lower()
    finally:
        termios.tcsetattr(
            fd, termios.TCSADRAIN, old_settings
        )  # pylint: disable=possibly-used-before-assignment
