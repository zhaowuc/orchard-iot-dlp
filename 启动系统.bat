@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "runtime\pythonw.exe" (
  echo 离线运行时不完整：未找到 runtime\pythonw.exe
  echo 请重新解压完整离线运行包。
  pause
  exit /b 1
)
start "" "runtime\pythonw.exe" "offline_launcher.pyw"
exit /b 0
