@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM
CD /D "%~dp0"

REM
py -3 --version >NUL 2>&1
IF %ERRORLEVEL% EQU 0 (
    SET "PY=py -3"
) ELSE (
    python --version >NUL 2>&1
    IF %ERRORLEVEL% EQU 0 (
        SET "PY=python"
    ) ELSE (
        ECHO No suitable Python interpreter found (tried py -3 and python).
        PAUSE
        EXIT /B 1
    )
)

REM
IF NOT EXIST "venv\Scripts\activate.bat" (
    ECHO Creating virtualenv…
    %PY% -m venv venv
    IF %ERRORLEVEL% NEQ 0 (
        ECHO Failed to create virtualenv!
        PAUSE
        EXIT /B 1
    )
)

REM
ECHO Activating virtualenv…
CALL venv\Scripts\activate.bat

REM
IF EXIST requirements.txt (
    ECHO Installing dependencies…
    pip install --upgrade pip
    pip install -r requirements.txt
)

REM
python -m plugins.resources.export_gui

PAUSE
