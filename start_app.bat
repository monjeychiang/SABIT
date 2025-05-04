@echo off
chcp 65001
echo 正在啟動加密貨幣交易系統...

REM 檢查環境配置
IF NOT EXIST backend\.env (
    echo 警告: 後端環境變數未配置，將複製示例文件...
    copy backend\.env.example backend\.env
    echo 請修改 backend\.env 文件配置您的API金鑰
)

REM 檢查後端是否已經運行
netstat -ano | findstr ":8000" > nul
if %errorlevel% equ 0 (
    echo 後端服務已經在運行中...
) else (
    echo 正在啟動後端服務...
    pushd backend
    start cmd /k "python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
    popd
    echo 等待後端服務啟動...
    timeout /t 5 /nobreak > nul
)

REM 檢查前端是否已經運行
netstat -ano | findstr ":5175" > nul
if %errorlevel% equ 0 (
    echo 前端服務已經在運行中...
) else (
    echo 正在啟動前端服務...
    pushd frontend
    start cmd /k "npm run dev"
    popd
)

echo 系統啟動成功！
echo 後端API服務運行於: http://127.0.0.1:8000
echo 前端UI服務運行於: http://127.0.0.1:5175
echo.
echo 按任意鍵打開瀏覽器訪問前端UI...
pause > nul
start http://127.0.0.1:5175

echo 按任意鍵關閉所有服務...
pause > nul

REM 關閉所有服務
FOR /F "tokens=5" %%T IN ('netstat -ano ^| findstr /r /c:"127.0.0.1:8000.*LISTENING"') DO taskkill /F /PID %%T > nul 2>&1
FOR /F "tokens=5" %%T IN ('netstat -ano ^| findstr /r /c:"127.0.0.1:5175.*LISTENING"') DO taskkill /F /PID %%T > nul 2>&1

echo 服務已關閉 