import argparse
import importlib.resources
import subprocess

path = str(importlib.resources.files("xpick") / "app.py")


def main():
    parser = argparse.ArgumentParser(description="A picking tool for DAS.")
    parser.add_argument("path", help="Path of the database to explore.")
    parser.add_argument(
        "--width", help="Width of the image in pixels.", type=int, default=1920
    )
    parser.add_argument(
        "--height", help="Height of the image in pixels.", type=int, default=1080
    )
    args, remaining_args = parser.parse_known_args()
    cmd = ["bokeh", "serve", path]
    extra = []
    for key, value in vars(args).items():
        extra.append(f"--{key}")
        extra.append(f"{value}")
    cmd = cmd + list(remaining_args) + ["--args"] + extra
    print(" ".join(cmd))
    subprocess.call(cmd)
