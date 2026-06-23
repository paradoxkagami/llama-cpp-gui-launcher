@echo off
chcp 65001 >nul
title Llama.cpp Server 启动器
cd /d "%~dp0"
python llama_launcher_gui.py
if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，请检查 Python 环境是否正确安装
    pause
)
