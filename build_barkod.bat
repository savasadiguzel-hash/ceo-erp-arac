@echo off
chcp 65001 > nul
echo CEO Barkod derleniyor...
echo.

python -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name "CEO-Barkod" ^
    --icon "assets\barkod.ico" ^
    --add-data "assets\logo.jpeg;assets" ^
    --hidden-import=pyodbc ^
    --hidden-import=PIL ^
    --hidden-import=qrcode ^
    --hidden-import=win32print ^
    --hidden-import=win32api ^
    --hidden-import=win32timezone ^
    --collect-submodules=barkod ^
    barkod_app.py

echo.
if %errorlevel% == 0 (
    echo TAMAMLANDI: dist\CEO-Barkod.exe
) else (
    echo HATA: Derleme basarisiz. Ciktiyi kontrol edin.
)
if not "%1"=="nopause" pause
