@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo ========================================
echo  Building Customer Acquisition System
echo ========================================
echo.

REM Use the project venv Python when available (fallback: system python)
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

REM Install PyInstaller if not present
"%PY%" -m pip install pyinstaller --quiet

REM Build (Flet desktop app via PyInstaller)
REM NOTE: .env / settings.json / exports / logs / memory are runtime data and
REM are intentionally NOT packaged into the executable.
"%PY%" -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "CustomerAcquisition" ^
    --add-data "industries;industries" ^
    --collect-all flet ^
    --collect-all flet_desktop ^
    --additional-hooks-dir hooks ^
    main.py

echo.
echo Build complete! Check dist\CustomerAcquisition\
echo.
pause
endlocal
