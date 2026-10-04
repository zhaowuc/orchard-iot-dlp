@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "runtime\pythonw.exe" (
  echo 离线运行时不完整：未找到 runtime\pythonw.exe
  pause
  exit /b 1
)
start "" "runtime\pythonw.exe" "offline_stop.pyw"
exit /b 0
