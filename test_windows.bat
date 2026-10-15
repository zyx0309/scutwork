@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" goto failed
".venv\Scripts\python.exe" -u "tools\launcher.py" --test
if errorlevel 1 goto failed
echo Tests passed on small synthetic fixtures. National real data is not validated by these tests.
pause
popd
exit /b 0
:failed
echo Tests failed. Check the installed environment and logs.
pause
popd
exit /b 1
