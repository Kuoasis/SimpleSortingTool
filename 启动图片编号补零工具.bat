@echo off
chcp 65001 >nul
cd /d "%~dp0"
py --version >nul 2>&1
if errorlevel 1 (
    python "图片编号补零工具.py"
) else (
    py "图片编号补零工具.py"
)
if errorlevel 1 pause
