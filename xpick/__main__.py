import argparse
import importlib.resources
import subprocess

path = str(importlib.resources.files("xpick") / "app")


def main():
    parser = argparse.ArgumentParser(
        description="""
        A picking tool for DAS.
        
        Not recognized options will passed to 'bokeh serve' (such as --port, --dev or 
        --show)
        """
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Path of the data arrays or one data collection to explore.",
    )
    parser.add_argument(
        "--width", help="Width of the image in pixels.", type=int, default=1080
    )
    parser.add_argument(
        "--height", help="Height of the image in pixels.", type=int, default=720
    )
    parser.add_argument(
        "--phases", help="List of phases to pick e.g., 'P,S'.", type=str, default="P,S"
    )
    parser.add_argument(
        "--colors",
        help="List of colors to pick e.g., '#7F0DFF,#FF00FF'.",
        type=str,
        default="",
    )
    args, remaining_args = parser.parse_known_args()
    cmd = ["bokeh", "serve", path]
    extra = []
    for key, value in vars(args).items():
        extra.append(f"--{key}")
        if isinstance(value, list):
            for element in value:
                extra.append(str(element))
        else:
            extra.append(str(value))
    cmd = cmd + list(remaining_args) + ["--args"] + extra
    subprocess.call(cmd)
