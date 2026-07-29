@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo ========================================
echo   获客自动化系统 v3.0
echo ========================================
echo.
set "PYEXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
"%PYEXE%" "%~dp0main.py"
if errorlevel 1 (
    echo.
    echo 启动失败, 请检查 Python 环境
    echo pip install -r requirements.txt
    pause
)
