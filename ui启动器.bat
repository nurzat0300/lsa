@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_BASE=%PYTHON_EXE% -m pip install --disable-pip-version-check --retries 2 --timeout 120"

echo [INFO] Project Dir: %CD%

if not exist "%PYTHON_EXE%" (
    echo [INFO] Creating virtual environment...
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 -m venv "%VENV_DIR%"
    ) else (
        python -m venv "%VENV_DIR%"
    )
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        echo [HINT] Please make sure Python 3 is installed and added to PATH.
        pause
        exit /b 1
    )
)

echo [INFO] Checking dependencies...
call :check_dependencies
if errorlevel 1 (
    echo [INFO] Installing/updating dependencies...
    call :install_requirements
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed after trying multiple package sources.
        echo [HINT] Detected proxy-related failures are common on Windows.
        echo [HINT] Check proxy env vars in current shell: set http_proxy ^& set https_proxy
        echo [HINT] You can run this once to set mirror permanently:
        echo        %PYTHON_EXE% -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
        echo [HINT] If your Python is too new for PyQt5, try Python 3.10 or 3.11.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Dependencies already satisfied. Skipping install.
)

echo [INFO] Starting UI...
"%PYTHON_EXE%" run.py --ui
set "APP_EXIT=%ERRORLEVEL%"

if not "%APP_EXIT%"=="0" (
    echo [ERROR] Application exited with code %APP_EXIT%.
    pause
    exit /b %APP_EXIT%
)

endlocal
exit /b 0

:check_dependencies
"%PYTHON_EXE%" -c "import PyQt5, networkx, matplotlib, numpy" >nul 2>nul
if errorlevel 1 (
    exit /b 1
)
exit /b 0

:install_requirements
echo [INFO] Try source: https://pypi.tuna.tsinghua.edu.cn/simple
%PIP_BASE% -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.txt
if not errorlevel 1 goto :install_ok

echo [WARN] Retry without proxy environment variables...
set "http_proxy="
set "https_proxy="
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "all_proxy="
%PIP_BASE% -r requirements.txt
if not errorlevel 1 goto :install_ok

echo [WARN] Official PyPI failed, trying Tsinghua mirror...
%PIP_BASE% -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.txt
if not errorlevel 1 goto :install_ok

echo [WARN] Tsinghua mirror failed, trying Aliyun mirror...
%PIP_BASE% -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com -r requirements.txt
if not errorlevel 1 goto :install_ok

echo [WARN] Aliyun mirror failed, trying USTC mirror...
%PIP_BASE% -i https://pypi.mirrors.ustc.edu.cn/simple --trusted-host pypi.mirrors.ustc.edu.cn -r requirements.txt
if not errorlevel 1 goto :install_ok

exit /b 1

:install_ok
exit /b 0
