@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" goto failed
".venv\Scripts\python.exe" -u "tools\launcher.py" --backup-outputs --collect-station-diagnostics
if errorlevel 1 goto failed
echo Completed. Review outputs\RESULTS.md.
echo Small review ZIP: outputs\submission\Station_Diagnostics.zip
pause
popd
exit /b 0
:failed
echo Processing failed. Keep the newest run log in logs.
pause
popd
exit /b 1
