#!/usr/bin/env python3
import os 
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
os.chdir(APP_DIR)

import socket
import subprocess
import sys
import time

APP_FILE = Path(__file__).parent / "app.py"
HOST = "127.0.0.1"
WINDOW_TITLE = "Pokemon Trading"
WINDOW_SIZE = (1080, 720)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def wait_for_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main():
    try:
        import webview
    except ImportError:
        sys.exit(
            "pywebview isn't installed.\n"
            "Install it with:  pip install pywebview\n"
            "Then re-run:      python desktop_launcher.py"
        )

    port = find_free_port()

    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(APP_FILE),
            "--server.headless=true",
            "--server.address",
            HOST,
            "--server.port",
            str(port),
            "--browser.gatherUsageStats=false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        if not wait_for_server(port):
            server.terminate()
            sys.exit("The app server didn't start in time. Try running `streamlit run app.py` directly to debug.")

        window = webview.create_window(
            WINDOW_TITLE,
            f"http://{HOST}:{port}",
            width=WINDOW_SIZE[0],
            height=WINDOW_SIZE[1],
            min_size=(1000, 700),
        )
        webview.start()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()