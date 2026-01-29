#!/bin/bash
# Start the frontend dev server

cd "$(dirname "$0")/../frontend"

echo "Starting AskDB frontend..."
echo "  - URL: http://localhost:5173"
echo ""

npm run dev
