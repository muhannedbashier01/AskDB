#!/bin/bash
# Stop all services

echo "Stopping services..."

# Stop Seq container (logging service)
# docker stop: stops the running container named "seq"
# 2>/dev/null: suppresses error messages if container doesn't exist
docker stop seq 2>/dev/null && echo "Stopped Seq"

# Kill backend process (uvicorn on port 8000)
# lsof -ti:8000: lists process IDs (-t) using port 8000 (-i:8000)
# xargs kill -9: forcefully terminates (-9) those processes
# 2>/dev/null: suppresses error messages if no process is found
lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "Stopped Backend"

# Kill frontend process (vite on port 5173)
# lsof -ti:5173: lists process IDs using port 5173
# xargs kill -9: forcefully kills those processes
# 2>/dev/null: suppresses error messages if no process is found
lsof -ti:5173 | xargs kill -9 2>/dev/null && echo "Stopped Frontend"

echo "All services stopped."
