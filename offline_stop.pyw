"""Stop the server started by offline_launcher.pyw."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import subprocess


BASE_DIR = Path(__file__).resolve().parent
PID_FILE = BASE_DIR / "work" / "offline_server.pid"
CREATE_NO_WINDOW = 0x08000000


def message(body: str, error: bool = False) -> None:
    if os.getenv("ORCHARD_DLP_SILENT") == "1":
        return
    ctypes.windll.user32.MessageBoxW(None, body, "果安哨兵", 0x10 if error else 0x40)


def main() -> None:
    if not PID_FILE.is_file():
        message("未发现由离线启动器运行的服务。")
        return
    try:
        pid = int(PID_FILE.read_text(encoding="ascii").strip())
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
        )
        PID_FILE.unlink(missing_ok=True)
        if result.returncode == 0:
            message("服务已停止。")
        else:
            message("服务进程已不存在，状态记录已清理。")
    except Exception as exc:
        message(f"停止服务失败：\n{exc}", True)


if __name__ == "__main__":
    main()
