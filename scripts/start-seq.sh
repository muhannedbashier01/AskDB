#!/bin/bash
# Start Seq logging server

CONTAINER_NAME="seq"

# Check if container exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Starting existing Seq container..."
    docker start $CONTAINER_NAME
else
    echo "Creating new Seq container..."
    docker run -d \
        --name $CONTAINER_NAME \
        -e ACCEPT_EULA=Y \
        -e SEQ_FIRSTRUN_NOAUTHENTICATION=true \
        -p 5341:5341 \
        -p 8080:80 \
        datalust/seq:latest
fi

echo ""
echo "Seq is running:"
echo "  - Web UI: http://localhost:8080"
echo "  - Ingestion: http://localhost:5341"
