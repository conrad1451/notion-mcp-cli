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
    else:  # macOS and Linux
        # import tty
        # import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
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
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
