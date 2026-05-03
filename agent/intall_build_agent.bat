@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul
title NHSO Agent Setup

echo ============================================================
echo   NHSO Local Agent Setup (Embedded Python)
echo ============================================================
echo.

set "PY_VER=3.13.3"
set "PY_ZIP=python-embed.zip"
set "PY_URL=https://www.python.org/ftp/python/%PY_VER%/python-%PY_VER%-embed-amd64.zip"
set "PY_DIR=python"
set "PY_EXE=%PY_DIR%\python.exe"

if not exist "%PY_EXE%" (
    echo [1/5] Downloading Python %PY_VER% embeddable...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_ZIP%' -UseBasicParsing"
    if errorlevel 1 (
        echo.
        echo [ERROR] Download failed.
        pause
        exit /b 1
    )
    if not exist "%PY_ZIP%" (
        echo.
        echo [ERROR] Download file not found: %PY_ZIP%
        pause
        exit /b 1
    )

    echo [2/5] Extracting Python...
    if not exist "%PY_DIR%" mkdir "%PY_DIR%"
    powershell -NoProfile -Command "Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%PY_DIR%' -Force"
    if errorlevel 1 (
        echo.
        echo [ERROR] Extract failed.
        pause
        exit /b 1
    )
    del /f /q "%PY_ZIP%" >nul 2>&1
) else (
    echo [SKIP] Embedded Python already exists.
)

if not exist "%PY_EXE%" (
    echo.
    echo [ERROR] python.exe not found after extract.
    pause
    exit /b 1
)

echo [3/5] Enabling site-packages in ._pth...
set "PTH_FOUND=0"
for %%f in ("%PY_DIR%\python*._pth") do (
    set "PTH_FOUND=1"
    powershell -NoProfile -Command "$p='%%~ff'; $c=Get-Content -LiteralPath $p; $c=$c -replace '#import site','import site'; Set-Content -LiteralPath $p -Value $c -Encoding Ascii"
)
if "%PTH_FOUND%"=="0" (
    echo [WARN] No python*._pth file found.
)

echo [4/5] Installing pip...
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py' -UseBasicParsing"
if errorlevel 1 (
    echo.
    echo [ERROR] Cannot download get-pip.py
    pause
    exit /b 1
)
"%PY_EXE%" get-pip.py --no-warn-script-location
if errorlevel 1 (
    echo.
    echo [ERROR] pip installation failed.
    del /f /q get-pip.py >nul 2>&1
    pause
    exit /b 1
)
del /f /q get-pip.py >nul 2>&1

echo [5/5] Installing packages: requests pyscard pythaiidcard ...
"%PY_EXE%" -m pip install --no-warn-script-location requests pyscard pythaiidcard
if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed.
    pause
    exit /b 1
)

echo.
echo Verifying imports...
"%PY_EXE%" -c "import requests, smartcard, pythaiidcard; print('OK')"
if errorlevel 1 (
    echo.
    echo [ERROR] Package verification failed.
    pause
    exit /b 1
)

echo.
echo Cleaning installer artifacts...
if exist "%PY_ZIP%" del /f /q "%PY_ZIP%" >nul 2>&1
if exist "get-pip.py" del /f /q "get-pip.py" >nul 2>&1
if exist "__pycache__" rmdir /s /q "__pycache__" >nul 2>&1

echo.
echo ============================================================
echo   Setup complete.
echo   Next: double-click Card_reader_agent.bat
echo ============================================================
pause
exit /b 0
