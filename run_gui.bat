@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

py -3 --version >NUL 2>&1 && set "PY=py -3" || (
  python --version >NUL 2>&1 && set "PY=python" || (
    echo No suitable Python interpreter found (tried py -3 and python)
    pause
    exit /b 1
  )
)

if not exist "venv\Scripts\activate.bat" (
  echo Creating virtualenv…
  %PY% -m venv venv || (
    echo Failed to create virtualenv!
    pause
    exit /b 1
  )
)
echo Activating virtualenv…
call venv\Scripts\activate.bat

if exist requirements.txt (
  echo Installing dependencies…
  pip install --upgrade pip
  pip install -r requirements.txt
)

set "API_TOKEN="
set "CFG1=%CD%\elapi.yml"
set "CFG2=%USERPROFILE%\.config\elapi.yml"
set "CFG3=%USERPROFILE%\.config\elapi\elapi.yml"
set "CFG4=%APPDATA%\elapi\elapi.yml"
set "CFG5=%PROGRAMDATA%\elapi\elapi.yml"

for %%P in (
  "%CFG1%" "%CFG2%" "%CFG3%" "%CFG4%" "%CFG5%"
) do (
  if exist %%~P (
    for /f "tokens=1* delims=:" %%A in ('findstr /I "^ *api_token *:" "%%~P"') do (
      set "cand=%%B"
      for /f "tokens=* delims= " %%C in ("!cand!") do set "cand=%%C"
      if defined cand (
        set "API_TOKEN=!cand!"
        echo ✔️  Found API token in %%~P
        goto :GOT_TOKEN
      )
    )
  )
)

:GOT_TOKEN
if not defined API_TOKEN (
  echo No API token found in known locations.
  echo Launching elapi init...

  chcp 65001 >nul

  color 1F
  echo.
  echo ************************************************************
  echo *                  UNI-HEIDELBERG USERS                    *
  echo *                                                          *
  echo *  Use this API address:                                   *
  echo *  https://elabftw.uni-heidelberg.de/api/v2                *
  echo ************************************************************
  echo.
  color 07

  set "OUTDIR=%USERPROFILE%\.config\elapi"
  set "CFG_INIT_FILE=!OUTDIR!\elapi.yml"
  if not exist "!OUTDIR!" mkdir "!OUTDIR!"
  if not exist "!CFG_INIT_FILE!" (
    echo host: https://elabftw.uni-heidelberg.de/api/v2>"!CFG_INIT_FILE!"
  ) else (
    findstr /C:"host:" "!CFG_INIT_FILE!" >nul || (
      echo host: https://elabftw.uni-heidelberg.de/api/v2>>"!CFG_INIT_FILE!"
    )
  )

  elapi init

  for %%P in (
    "%CFG1%" "%CFG2%" "%CFG3%" "%CFG4%" "%CFG5%"
  ) do (
    if exist %%~P (
      for /f "tokens=1* delims=:" %%A in ('findstr /I "^ *api_token *:" "%%~P"') do (
        set "cand=%%B"
        for /f "tokens=* delims= " %%C in ("!cand!") do set "cand=%%C"
        if defined cand (
          set "API_TOKEN=!cand!"
          echo Found API token in %%~P after elapi init
          goto :GOT_TOKEN
        )
      )
    )
  )

  echo Could not retrieve API token after elapi init. Aborting.
  pause
  exit /b 1
)

set "ELAPI_API_TOKEN=%API_TOKEN%"

echo Running GUI…
python -m gui.gui

endlocal
exit /b 0
