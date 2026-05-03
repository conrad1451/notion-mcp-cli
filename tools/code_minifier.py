import sys
from pathlib import Path
import python_minifier

"""Minifies Python source files using python_minifier."""


def minify_file(input_path, output_path):
    """Minify a Python file and write the result to output_path."""
    try:
        # Read the original Python code
        code = Path(input_path).read_text(encoding="utf-8")

        # Minify the code
        minified_code = python_minifier.minify(
            code,
            remove_literal_statements=True,  # Removes docstrings
            remove_annotations=True,  # Removes type hints
            combine_imports=True,  # Combines imports
            hoist_literals=True,  # Hoists repeated literals
        )

        # Save the minified code
        Path(output_path).write_text(minified_code, encoding="utf-8")
        print(f"Minified code saved to {output_path}")

    except FileNotFoundError:
        print(f"Error: File '{input_path}' not found.")
    except (ValueError, python_minifier.UnstableMinification) as e:
        print(f"Minification failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python minify.py <input_file.py> <output_file.py>")
    else:
        minify_file(sys.argv[1], sys.argv[2])
