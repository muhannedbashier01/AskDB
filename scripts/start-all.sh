#!/bin/bash
# Start all services (Seq, Backend, Frontend)

SCRIPT_DIR="$(dirname "$0")"

echo "========================================="
echo "  Starting AskDB Development Environment"
echo "========================================="
echo ""

# Start Seq
echo "[1/3] Starting Seq..."
$SCRIPT_DIR/start-seq.sh
echo ""

# Start backend in background
echo "[2/3] Starting Backend..."
osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR/..' && $SCRIPT_DIR/start-backend.sh\"" 2>/dev/null || \
    (echo "Run in new terminal: ./scripts/start-backend.sh")
echo ""

# Start frontend in background
echo "[3/3] Starting Frontend..."
osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR/..' && $SCRIPT_DIR/start-frontend.sh\"" 2>/dev/null || \
    (echo "Run in new terminal: ./scripts/start-frontend.sh")
echo ""

echo "========================================="
echo "  Services:"
echo "    - Seq:      http://localhost:8080"
echo "    - Backend:  http://localhost:8000"
echo "    - Frontend: http://localhost:5173"
echo "========================================="
