import click

from client import DEBUG


def debug(msg):
    """
    Prints a debug message to the console if the DEBUG environment variable is enabled.

    Args:
        msg (str): The message to display.
    """
    if DEBUG:
        click.echo(f"[DEBUG] {msg}")
