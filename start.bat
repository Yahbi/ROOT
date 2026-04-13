@echo off
REM Portable Windows launcher — works from any clone location.
setlocal

REM cd to the directory this script lives in.
cd /d "%~dp0"

REM Activate venv if present.
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

if "%ROOT_HOST%"=="" set ROOT_HOST=127.0.0.1
if "%ROOT_PORT%"=="" set ROOT_PORT=9000

uvicorn backend.main:app --host %ROOT_HOST% --port %ROOT_PORT%
endlocal
