@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" goto failed
".venv\Scripts\python.exe" -u "tools\launcher.py" --test
if errorlevel 1 goto failed
echo 测试通过。这仅验证小型人工测试数据，不表示全国真实数据已验证。
pause
popd
exit /b 0
:failed
echo 测试未完成。请先安装环境，并查看 logs 日志。
pause
popd
exit /b 1
