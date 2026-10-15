@echo off
call "%~dp0run.bat" --backup-outputs %*
exit /b %errorlevel%
