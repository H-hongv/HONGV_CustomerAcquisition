@echo off
echo ========================================
echo  Building Customer Acquisition System
echo ========================================

REM Install PyInstaller if not present
pip install pyinstaller --quiet

REM Build
pyinstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "CustomerAcquisition" ^
    --add-data "industries;industries" ^
    --add-data ".env;.env" ^
    --hidden-import=PyQt5 ^
    --hidden-import=PyQt5.QtWidgets ^
    --hidden-import=PyQt5.QtCore ^
    --hidden-import=PyQt5.QtGui ^
    main.py

echo.
echo Build complete! Check dist\CustomerAcquisition\
echo.
pause
