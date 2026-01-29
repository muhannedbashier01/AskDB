#!/bin/bash
# Start the FastAPI backend

cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "Starting AskDB backend..."
echo "  - API: http://localhost:8000"
echo "  - Docs: http://localhost:8000/docs"
echo ""

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
