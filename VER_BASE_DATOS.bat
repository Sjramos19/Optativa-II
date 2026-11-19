@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
py -3 "%~dp0ver_base_datos.py"
pause
