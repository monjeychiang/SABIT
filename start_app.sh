#!/bin/bash

# Add execute permission to the script
chmod +x "$0"

echo "Starting SABIT Crypto Trading System..."

# Check if .env file exists
if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    echo "Created environment config file"
fi

# Start backend service
echo "Starting backend service..."
cd backend
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend initialization
echo "Waiting for backend service..."
sleep 3

# Start frontend service
echo "Starting frontend service..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Display success information
echo ""
echo "System started successfully!"
echo "Backend API: http://127.0.0.1:8000"
echo "Frontend UI: http://127.0.0.1:5175"
echo "API Docs:    http://127.0.0.1:8000/docs"
echo ""

# Ask to open browser
read -p "Open browser to access frontend UI? (Y/N) " OPEN_BROWSER
if [[ $OPEN_BROWSER =~ ^[Yy]$ ]]; then
    # Open browser based on OS
    if [ "$(uname)" == "Darwin" ]; then # macOS
        open "http://127.0.0.1:5175"
    elif [ "$(uname)" == "Linux" ]; then # Linux
        xdg-open "http://127.0.0.1:5175" 2>/dev/null || \
        sensible-browser "http://127.0.0.1:5175" 2>/dev/null || \
        firefox "http://127.0.0.1:5175" 2>/dev/null || \
        google-chrome "http://127.0.0.1:5175" 2>/dev/null
    fi
fi

# Define function to handle SIGINT signal
function cleanup() {
    echo ""
    echo "Closing all services..."
    
    # Terminate all related processes
    if [ -n "$BACKEND_PID" ]; then
        echo "Closing backend service (PID: $BACKEND_PID)..."
        kill -TERM $BACKEND_PID 2>/dev/null || kill -KILL $BACKEND_PID 2>/dev/null
    else
        pkill -f "uvicorn app.main:app" 2>/dev/null
    fi
    
    if [ -n "$FRONTEND_PID" ]; then
        echo "Closing frontend service (PID: $FRONTEND_PID)..."
        kill -TERM $FRONTEND_PID 2>/dev/null || kill -KILL $FRONTEND_PID 2>/dev/null
    else
        pkill -f "node.*vite" 2>/dev/null
    fi
    
    echo "All services closed"
    exit 0
}

# Register signal handler
trap cleanup INT TERM

echo ""
echo "System is now running. Press Ctrl+C to stop all services."

# Keep script running until user presses Ctrl+C
wait 