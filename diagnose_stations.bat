@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" goto failed
".venv\Scripts\python.exe" -u "tools\launcher.py" --diagnose-stations
if errorlevel 1 goto failed
echo Diagnostic ZIP: outputs\submission\Station_Diagnostics.zip
pause
popd
exit /b 0
:failed
echo Diagnostics failed. Keep the newest diagnostics log in logs.
pause
popd
exit /b 1
