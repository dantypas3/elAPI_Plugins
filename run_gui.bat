@echo off
setlocal

cd /d "%~dp0"

py -3 --version >NUL 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY=py -3"
) else (
    python --version >NUL 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PY=python"
    ) else (
        echo No suitable Python. interpreter found (tried py -3 and python)
        pause
        exit /b 1
    )
)

if not exist "venv\Scripts\activate.bat" (
    echo Creating virtualenv
    %PY% -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to create virtualenv!
        pause
        exit /b 1
    )
)

echo Activating virtualenv
call venv\Scripts\activate.bat

if exist requirements.txt (
    echo Installing dependencies
    pip install --upgrade pip
    pip install -r requirements.txt
)

echo Running export_gui
python -m gui.gui

exit