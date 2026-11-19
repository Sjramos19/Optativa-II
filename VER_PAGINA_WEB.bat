@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"

echo ========================================================
echo        TECHSTORE - SISTEMA WEB LOCAL (MOMENTO 2)
echo ========================================================
echo.
echo Iniciando servidor local y abriendo navegador en http://localhost:8000 ...
echo.
echo Presione Ctrl+C en esta ventana para cerrar el servidor cuando termine.
echo ========================================================
echo.

py -3 "%~dp0web_app.py"
if errorlevel 1 (
    echo.
    echo No se pudo iniciar con "py -3". Intentando con "python"...
    python "%~dp0web_app.py"
)

pause
