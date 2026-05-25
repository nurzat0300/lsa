@echo off
chcp 65001 >nul
cd /d "%~dp0"

title 链路状态路由协议仿真系统

echo ============================================
echo   链路状态路由协议分布式仿真系统
echo   Link State Routing Protocol Simulator
echo ============================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo [启动] 使用虚拟环境 Python ...
    ".venv\Scripts\python.exe" run.py --ui
) else (
    echo [启动] 使用系统 Python ...
    python run.py --ui
)

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，错误码: %ERRORLEVEL%
    echo [提示] 如果首次运行，请先双击 "ui启动器.bat" 自动安装依赖。
    pause
)
