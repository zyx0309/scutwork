@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
echo Preparing Python 3.12 64-bit environment...
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto use_python
py -3.12 -m venv ".venv"
if errorlevel 1 goto failed
goto install
:use_python
python -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto missing_python
python -m venv ".venv"
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -u "tools\launcher.py" --install
if errorlevel 1 goto failed
echo.
echo Installed. Put both PBF files in data\raw and run run.bat.
pause
popd
exit /b 0
:missing_python
echo Python 3.12 64-bit not found. Install from https://www.python.org/downloads/ and enable Add python.exe to PATH.
goto failed
:failed
echo.
echo Installation failed. Read the messages above and the logs folder.
pause
popd
exit /b 1
