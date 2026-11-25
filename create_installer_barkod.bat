@echo off
chcp 65001 > nul
echo CEO Barkod - Kurulum paketi olusturuluyor...
echo.

set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if %ISCC%=="" (
    echo HATA: Inno Setup 6 bulunamadi.
    if not "%1"=="nopause" pause
    exit /b 1
)

if not exist "dist\CEO-Barkod.exe" (
    echo HATA: dist\CEO-Barkod.exe bulunamadi. Once build_barkod.bat calistirin.
    if not "%1"=="nopause" pause
    exit /b 1
)
if not exist "dist\config.json" (
    echo HATA: dist\config.json bulunamadi.
    if not "%1"=="nopause" pause
    exit /b 1
)

%ISCC% setup_barkod.iss

if %errorlevel% == 0 (
    echo.
    echo TAMAMLANDI: dist\CEO-Barkod-Kurulum.exe
) else (
    echo.
    echo HATA: Kurulum paketi derlenemedi.
)
if not "%1"=="nopause" pause
