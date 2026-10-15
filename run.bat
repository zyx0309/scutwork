@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_environment
echo Processing local PBF files. No automatic download. The first scan can take a long time.
".venv\Scripts\python.exe" -u "tools\launcher.py" %*
if errorlevel 1 goto failed
echo.
echo Completed. See outputs\run_status.json, outputs\RESULTS.md and outputs\figures.
pause
popd
exit /b 0
:missing_environment
echo Please run install.bat first.
:failed
echo.
echo Processing failed. Keep the newest run and errors files in logs. Press a key to close.
pause
popd
exit /b 1
