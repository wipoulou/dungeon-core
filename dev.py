"""Dev runner: restarts main.py on code changes."""

import subprocess
import sys

from watchfiles import run_process


def run_game():
    subprocess.run([sys.executable, "main.py"])


if __name__ == "__main__":
    print("Watching for changes... (Ctrl+C to stop)")
    run_process(".", target=run_game, watch_filter=lambda _, path: path.endswith(".py"))
