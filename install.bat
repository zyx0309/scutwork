@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
echo 正在准备 Python 3.12 64 位环境...
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
echo 安装完成。请将两个 PBF 放入 data\raw 后双击 run.bat。
pause
popd
exit /b 0
:missing_python
echo 未找到 Python 3.12 64 位。请从 https://www.python.org/downloads/ 安装，并勾选 Add python.exe to PATH。
goto failed
:failed
echo.
echo 安装未完成。请查看上方信息及 logs 文件夹中的日志。
pause
popd
exit /b 1
