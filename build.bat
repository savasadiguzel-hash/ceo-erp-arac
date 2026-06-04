@echo off
chcp 65001 > nul
echo CEO ERP Araclar derleniyor...
echo.

python -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name "CEO-ERP-Araclar" ^
    --hidden-import=pyodbc ^
    --hidden-import=PIL ^
    --hidden-import=PIL._tkinter_finder ^
    --collect-all win32com ^
    main.py

echo.
if %errorlevel% == 0 (
    copy /Y config.json dist\config.json > nul
    echo TAMAMLANDI: dist\CEO-ERP-Araclar.exe
) else (
    echo HATA: Derleme basarisiz. Ciktiyi kontrol edin.
)
pause
