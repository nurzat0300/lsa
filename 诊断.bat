@echo off
chcp 65001 >/dev/null
cd /d "%~dp0"

title 链路状态路由协议仿真系统 - 诊断模式

echo ============================================
echo   诊断模式 - 系统环境检查
echo ============================================
echo.

echo [1/5] 检查 Python ...
where python >/dev/null 2>/dev/null
if %errorlevel%==0 (
    python --version
) else (
    echo   [失败] 未找到 Python
)

echo.
echo [2/5] 检查虚拟环境 ...
if exist ".venv\Scripts\python.exe" (
    echo   [OK] 虚拟环境已存在
    set "PY=.venv\Scripts\python.exe"
) else (
    echo   [信息] 虚拟环境不存在，将使用系统 Python
    set "PY=python"
)

echo.
echo [3/5] 检查依赖 ...
%PY% -c "import PyQt5; print('  PyQt5:', PyQt5.QtCore.PYQT_VERSION_STR)" 2>/dev/null || echo   [失败] PyQt5 未安装
%PY% -c "import networkx; print('  networkx:', networkx.__version__)" 2>/dev/null || echo   [失败] networkx 未安装
%PY% -c "import matplotlib; print('  matplotlib:', matplotlib.__version__)" 2>/dev/null || echo   [失败] matplotlib 未安装
%PY% -c "import numpy; print('  numpy:', numpy.__version__)" 2>/dev/null || echo   [失败] numpy 未安装

echo.
echo [4/5] 检查配置文件 ...
if exist "config\network_topology.json" (echo   [OK] 默认拓扑配置存在) else (echo   [失败] config\network_topology.json 不存在)

echo.
echo [5/5] 检查端口占用 ...
netstat -ano 2>/dev/null | findstr "127.0.0.1:210" >/dev/null 2>/dev/null
if %errorlevel%==0 (
    echo   [警告] 检测到 210xx 端口可能被占用
) else (
    echo   [OK] 默认端口范围未被占用
)

echo.
echo ============================================
echo   诊断完成。按任意键尝试启动程序...
echo ============================================
pause >/dev/null

echo [启动] 正在启动仿真系统...
%PY% run.py --ui 2>&1
if errorlevel 1 (
    echo [错误] 程序退出码: %ERRORLEVEL%
    pause
)
