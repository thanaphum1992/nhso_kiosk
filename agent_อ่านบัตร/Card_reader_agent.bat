@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul

set "AGENT_DIR=%~dp0"
if exist "%AGENT_DIR%agent.log" del /f /q "%AGENT_DIR%agent.log"
set "PYTHON_EXE=%AGENT_DIR%python\python.exe"
set "SERVER_URL="

if not exist "config.ini" (
    echo [INFO] config.ini not found. Creating default config.ini ...
    echo [agent]> "config.ini"
    echo server_url = http://localhost:8222>> "config.ini"
    echo smartcard_agent_url = http://localhost:8189>> "config.ini"
    echo client_id =>> "config.ini"
    echo dep_code =>> "config.ini"
    echo poll_interval_sec = 0.8>> "config.ini"
    echo card_settle_delay_sec = 1.5>> "config.ini"
    echo.
    echo --- config.ini created with default settings ---
    echo [1] Please open config.ini and set server_url to your Server IP
    echo [2] Save the file, then press any key here to continue...
    echo.
    pause
)

REM Read config.ini (handling spaces around =)
if exist "config.ini" (
    for /f "usebackq tokens=1,2 delims==" %%a in ("config.ini") do (
        set "key=%%a"
        set "val=%%b"
        set "key=!key: =!"
        if /i "!key!"=="server_url" set "SERVER_URL=!val: =!"
        if /i "!key!"=="client_id" set "CLIENT_ID_CONFIG=!val: =!"
    )
)

if not defined SERVER_URL set "SERVER_URL=http://localhost:8222"
if not defined CLIENT_ID_CONFIG set "CLIENT_ID_CONFIG=%COMPUTERNAME%"

REM If embedded Python is missing, run setup automatically
if not exist "%PYTHON_EXE%" (
    echo.
    echo [INFO] Embedded Python not found. Running build_agent.bat ...
    call "%AGENT_DIR%build_agent.bat"
    if errorlevel 1 (
        echo.
        echo [ERROR] Setup failed. Cannot start local agent.
        echo         Please check network/firewall and run build_agent.bat again.
        echo.
        pause
        exit /b 1
    )
)

if not exist "%PYTHON_EXE%" (
    echo.
    echo [ERROR] Setup finished but python\python.exe is still missing.
    echo.
    pause
    exit /b 1
)

if not exist "%AGENT_DIR%local_agent.py" (
    echo.
    echo [ERROR] local_agent.py not found in:
    echo         %AGENT_DIR%
    echo.
    echo Copy the whole agent folder from the project, at minimum:
    echo   local_agent.py
    echo   Card_reader_agent.bat
    echo   build_agent.bat
    echo   config.ini
    echo   python\          ^(run build_agent.bat once if missing^)
    echo.
    echo Do NOT copy only dist\Card_reader_agent\ — that folder is for .exe build only.
    echo.
    pause
    exit /b 2
)

set "KIOSK_URL=%SERVER_URL%/kiosk?client_id=%CLIENT_ID_CONFIG%"
echo Kiosk URL: %KIOSK_URL%

set "CHROME_FLAGS=--noerrdialogs --disable-infobars --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required"
set "CHROME1=C:\Program Files\Google\Chrome\Application\chrome.exe"
set "CHROME2=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
set "CHROME3=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"

if exist "%CHROME1%" ( start "" "%CHROME1%" %CHROME_FLAGS% "%KIOSK_URL%" )
if not exist "%CHROME1%" if exist "%CHROME2%" ( start "" "%CHROME2%" %CHROME_FLAGS% "%KIOSK_URL%" )
if not exist "%CHROME1%" if not exist "%CHROME2%" if exist "%CHROME3%" ( start "" "%CHROME3%" %CHROME_FLAGS% "%KIOSK_URL%" )
if not exist "%CHROME1%" if not exist "%CHROME2%" if not exist "%CHROME3%" if exist "%EDGE%" (
    start "" "%EDGE%" "%KIOSK_URL%" --no-first-run --autoplay-policy=no-user-gesture-required
)
if not exist "%CHROME1%" if not exist "%CHROME2%" if not exist "%CHROME3%" if not exist "%EDGE%" (
    start "" "%KIOSK_URL%"
)

echo Starting NHSO Local Card Agent...
set "PYTHONIOENCODING=utf-8"
"%PYTHON_EXE%" local_agent.py
set "AGENT_EXIT=%ERRORLEVEL%"
if not "%AGENT_EXIT%"=="0" (
    echo.
    echo [ERROR] local_agent.py exited with code %AGENT_EXIT%
    echo         Check agent.log in this folder for details.
    echo.
    pause
    exit /b %AGENT_EXIT%
)

endlocal
exit /b 0
