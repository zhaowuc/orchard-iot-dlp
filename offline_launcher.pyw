"""Launch the self-contained Windows demo package without a console window."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser


BASE_DIR = Path(__file__).resolve().parent
RUNTIME = BASE_DIR / "runtime" / "python.exe"
MANAGE = BASE_DIR / "manage.py"
LOG_DIR = BASE_DIR / "logs"
PID_FILE = BASE_DIR / "work" / "offline_server.pid"
PORT = int(os.getenv("ORCHARD_DLP_PORT", "8000"))
ADDRESS = f"127.0.0.1:{PORT}"
URL = f"http://{ADDRESS}/accounts/login/"
CREATE_NO_WINDOW = 0x08000000


def message(title: str, body: str, error: bool = False) -> None:
    if os.getenv("ORCHARD_DLP_SILENT") == "1":
        return
    flags = 0x10 if error else 0x40
    ctypes.windll.user32.MessageBoxW(None, body, title, flags)


def site_is_ready() -> bool:
    try:
        with urllib.request.urlopen(URL, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def port_is_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1):
            return True
    except OSError:
        return False


def run_setup(log) -> None:
    for arguments in (["migrate", "--noinput"], ["seed_demo"]):
        result = subprocess.run(
            [str(RUNTIME), str(MANAGE), *arguments],
            cwd=BASE_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
            timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(f"manage.py {' '.join(arguments)} failed: {result.returncode}")


def main() -> None:
    if not RUNTIME.is_file():
        message("果安哨兵", "离线运行时不完整：未找到 runtime\\python.exe。请重新解压完整安装包。", True)
        return
    LOG_DIR.mkdir(exist_ok=True)
    PID_FILE.parent.mkdir(exist_ok=True)

    if site_is_ready():
        if os.getenv("ORCHARD_DLP_NO_BROWSER") != "1":
            webbrowser.open(URL)
        return
    if port_is_open():
        message("果安哨兵", f"端口 {PORT} 已被其他程序占用，请先关闭占用程序后重试。", True)
        return

    try:
        with (LOG_DIR / "offline_launcher.log").open("a", encoding="utf-8") as log:
            log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] offline startup\n")
            log.flush()
            run_setup(log)
            process = subprocess.Popen(
                [str(RUNTIME), str(MANAGE), "runserver", ADDRESS, "--noreload"],
                cwd=BASE_DIR,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            PID_FILE.write_text(str(process.pid), encoding="ascii")
    except Exception as exc:
        message("果安哨兵启动失败", f"启动过程中发生错误：\n{exc}\n\n请查看 logs\\offline_launcher.log。", True)
        return

    for _ in range(40):
        if site_is_ready():
            if os.getenv("ORCHARD_DLP_NO_BROWSER") != "1":
                webbrowser.open(URL)
            return
        if process.poll() is not None:
            break
        time.sleep(0.5)
    message("果安哨兵启动失败", "服务未能在 20 秒内启动，请查看 logs\\offline_launcher.log。", True)


if __name__ == "__main__":
    main()
