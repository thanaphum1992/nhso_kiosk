@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul

set "AGENT_DIR=%~dp0"
set "PYTHON_EXE=%AGENT_DIR%python\python.exe"
set "SERVER_URL="

REM Read server_url from config.ini (works even with [agent] section)
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /i /b "server_url=" "config.ini"`) do (
    set "SERVER_URL=%%b"
)
if not defined SERVER_URL set "SERVER_URL=http://localhost:8222"
set "SERVER_URL=%SERVER_URL: =%"

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
    echo         Please run build_agent.bat again.
    echo.
    pause
    exit /b 1
)

set "KIOSK_URL=%SERVER_URL%/kiosk?client_id=%COMPUTERNAME%"
echo Kiosk URL: %KIOSK_URL%

set "CHROME_FLAGS=--kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required"
set "CHROME1=C:\Program Files\Google\Chrome\Application\chrome.exe"
set "CHROME2=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
set "CHROME3=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"

if exist "%CHROME1%" ( start "" "%CHROME1%" %CHROME_FLAGS% "%KIOSK_URL%" )
if not exist "%CHROME1%" if exist "%CHROME2%" ( start "" "%CHROME2%" %CHROME_FLAGS% "%KIOSK_URL%" )
if not exist "%CHROME1%" if not exist "%CHROME2%" if exist "%CHROME3%" ( start "" "%CHROME3%" %CHROME_FLAGS% "%KIOSK_URL%" )
if not exist "%CHROME1%" if not exist "%CHROME2%" if not exist "%CHROME3%" if exist "%EDGE%" (
    start "" "%EDGE%" --kiosk "%KIOSK_URL%" --edge-kiosk-type=fullscreen --no-first-run --autoplay-policy=no-user-gesture-required
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
