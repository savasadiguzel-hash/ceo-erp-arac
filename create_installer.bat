@echo off
chcp 65001 > nul
echo CEO ERP Araclari — Kurulum paketi olusturuluyor...
echo.

REM Inno Setup 6 derleyicisini bul
set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if %ISCC%=="" (
    echo HATA: Inno Setup 6 bulunamadi.
    echo Lutfen https://jrsoftware.org/isdl.php adresinden indirip kurun.
    pause
    exit /b 1
)

REM dist\CEO-ERP-Araclar.exe mevcut mu?
if not exist "dist\CEO-ERP-Araclar.exe" (
    echo HATA: dist\CEO-ERP-Araclar.exe bulunamadi.
    echo Once build.bat calistirin.
    pause
    exit /b 1
)

echo Inno Setup derleniyor: setup.iss
%ISCC% setup.iss

if %errorlevel% == 0 (
    echo.
    echo TAMAMLANDI: dist\CEO-ERP-Kurulum.exe
) else (
    echo.
    echo HATA: Kurulum paketi derlenemedi.
)
pause
