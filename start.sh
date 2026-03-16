#!/bin/bash
# Start the Qdrant MCP Server

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the server
python server.py
