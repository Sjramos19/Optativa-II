@echo off
chcp 65001 >nul
title TechStore ERP
cd /d "%~dp0"

echo.
echo  ════════════════════════════════════════════════
echo         TECHSTORE ERP — Sistema de Ventas
echo  ════════════════════════════════════════════════
echo.

py -3 web_app.py

if errorlevel 1 (
  echo.
  echo  ERROR: No se pudo iniciar el servidor.
  echo  Instala Python 3.9+ desde python.org
  echo.
  pause
)
