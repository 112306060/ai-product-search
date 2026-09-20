@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
setlocal

echo ================================================
echo   AI 海外品牌搜尋系統
echo ================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 找不到 Python，這台電腦似乎還沒安裝 Python。
    echo.
    echo 請先到 https://www.python.org/downloads/ 下載並安裝
    echo Python 3.13 版本（安裝時務必勾選 "Add Python to PATH"）。
    echo 安裝完成後，重新雙擊本檔案即可。
    echo.
    pause
    exit /b 1
)

python launcher.py

echo.
pause
