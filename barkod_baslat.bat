@echo off
rem CEO Barkod programini baslatir (gelistirme surumu)
cd /d "%~dp0"
python barkod_app.py
if errorlevel 1 pause
