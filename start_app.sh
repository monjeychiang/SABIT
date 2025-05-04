#!/bin/bash

echo "正在啟動加密貨幣交易系統..."

echo "檢查環境配置..."
if [ ! -f backend/.env ]; then
    echo "警告: 後端環境變數未配置，將複製示例文件..."
    cp backend/.env.example backend/.env
    echo "請修改 backend/.env 文件配置您的API金鑰"
fi

echo "檢查後端是否已經運行..."
if netstat -tuln | grep ":8000" > /dev/null; then
    echo "後端服務已經在運行中..."
else
    echo "正在啟動後端服務..."
    cd backend
    # 以後台方式執行後端
    python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
    BACKEND_PID=$!
    cd ..

    echo "等待後端服務啟動..."
    sleep 5
fi

echo "檢查前端是否已經運行..."
if netstat -tuln | grep ":5175" > /dev/null; then
    echo "前端服務已經在運行中..."
else
    echo "正在啟動前端服務..."
    cd frontend
    # 以後台方式執行前端
    npm run dev &
    FRONTEND_PID=$!
    cd ..
fi

echo "系統啟動成功！"
echo "後端API服務運行於: http://127.0.0.1:8000"
echo "前端UI服務運行於: http://127.0.0.1:5175"
echo ""
echo "正在打開瀏覽器..."
# 嘗試使用不同的命令打開瀏覽器，適應不同的操作系統
if [ "$(uname)" == "Darwin" ]; then
    # macOS
    open http://127.0.0.1:5175
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    # Linux
    xdg-open http://127.0.0.1:5175 2>/dev/null || sensible-browser http://127.0.0.1:5175 2>/dev/null || firefox http://127.0.0.1:5175 2>/dev/null || google-chrome http://127.0.0.1:5175 2>/dev/null
fi

echo "按 Ctrl+C 停止所有服務"

# 捕獲 SIGINT 信號 (Ctrl+C)
trap cleanup INT

cleanup() {
    echo ""
    echo "正在關閉服務..."
    # 終止後端進程
    pkill -f "uvicorn app.main:app"
    # 終止前端進程 
    pkill -f "node.*dev"
    echo "服務已關閉"
    exit 0
}

# 保持腳本運行
wait 