@echo off
chcp 65001
title SABIT Trading System Launcher

echo Starting SABIT Crypto Trading System...

REM Check if .env file exists, copy template if not
if not exist backend\.env (
    copy backend\.env.example backend\.env
    echo Created environment config file
)

REM Start backend service directly
echo Starting backend service...
pushd backend
start cmd /k "title SABIT Backend Service & python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
popd

REM Wait for backend service to start
echo Waiting for backend service...
timeout /t 3 /nobreak > nul

REM Start frontend service directly
echo Starting frontend service...
pushd frontend
start cmd /k "title SABIT Frontend Service & npm run dev"
popd

echo.
echo System started successfully!
echo Backend API: http://127.0.0.1:8000
echo Frontend UI: http://127.0.0.1:5175
echo API Docs:    http://127.0.0.1:8000/docs
echo.

REM Ask if browser should be opened
set /p OPEN_BROWSER="Open browser to access frontend UI? (Y/N) "
if /i "%OPEN_BROWSER%"=="Y" (
    start http://127.0.0.1:5175
)

echo.
echo System is now running. Press any key to stop all services...
pause > nul

REM Close all services
echo Closing all services...
FOR /F "tokens=5" %%T IN ('netstat -ano ^| findstr /r /c:"127.0.0.1:8000.*LISTENING"') DO (
    taskkill /F /PID %%T > nul 2>&1
)

FOR /F "tokens=5" %%T IN ('netstat -ano ^| findstr /r /c:"127.0.0.1:5175.*LISTENING"') DO (
    taskkill /F /PID %%T > nul 2>&1
)

echo All services closed. 