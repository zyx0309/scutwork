@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_environment
echo 开始处理本地 PBF。不自动联网下载；大型数据首次扫描需要时间。
".venv\Scripts\python.exe" -u "tools\launcher.py" %*
if errorlevel 1 goto failed
echo.
echo 处理完成。请先打开 outputs\run_status.json 和 outputs\RESULTS.md，再查看 outputs\figures。
pause
popd
exit /b 0
:missing_environment
echo 请先双击 install.bat 完成安装。
:failed
echo.
echo 本次处理未成功。请保存 logs 中最新的 run 和 errors 日志。窗口保留，按任意键关闭。
pause
popd
exit /b 1
