@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "LOCAL_MEU=%SCRIPT_DIR%meu.py"

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PY_BIN=python"
) else (
    where py >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set "PY_BIN=py -3"
    ) else (
        echo [HATA] Python 3 bulunamadi. Lutfen Python 3 kurun ve tekrar deneyin.
        exit /b 1
    )
)

if exist "%LOCAL_MEU%" (
    %PY_BIN% "%LOCAL_MEU%" self-install
    exit /b %ERRORLEVEL%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1"
exit /b %ERRORLEVEL%
