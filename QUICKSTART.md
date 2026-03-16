# Quick Start Guide

Get the Qdrant MCP Server running in 5 minutes.

## Option 1: Using Docker Compose (Recommended)

### Start Qdrant + Ollama

```bash
# Start both services in background
docker-compose up -d

# Wait for services to be healthy (takes ~30s for Ollama to initialize)
docker-compose logs -f

# Once both are healthy, press Ctrl+C
```

### Install and run the MCP server

```bash
# Install Python dependencies
pip install -e .

# Run the server
python server.py
```

### Verify it works

In another terminal, test with the MCP Inspector:

```bash
uv run mcp dev server.py
```

Open [http://localhost:5173](http://localhost:5173) and test the tools.

## Option 2: Local Installation

### Install Qdrant

```bash
# On macOS with Homebrew
brew install qdrant

# Start Qdrant
qdrant --config-path ./qdrant-config.yaml
```

Or use [Qdrant Cloud](https://cloud.qdrant.io/). Set `QDRANT_URL` and `QDRANT_API_KEY` accordingly.

### Install Ollama

```bash
# macOS: Download from https://ollama.ai
# Linux: curl -fsSL https://ollama.ai/install.sh | sh

# Pull embedding model
ollama pull nomic-embed-text

# Start Ollama
ollama serve
```

### Run MCP Server

```bash
# Install dependencies
pip install -e .

# Set environment variables
export QDRANT_URL=http://localhost:6333
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=nomic-embed-text

# Run server
python server.py
```

## Test in Claude Desktop

1. Add to `~/.claude/mcp_servers.json`:

```json
{
  "mcpServers": {
    "qdrant": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

2. Restart Claude Desktop

3. Try asking: "Search for documents about machine learning in the 'ml_papers' collection"

## Troubleshooting

### Ollama slow on first run?

Ollama downloads the model on first use. This can take 1-5 minutes depending on your connection.

```bash
# Check model download
curl http://localhost:11434/api/tags

# Wait for `nomic-embed-text` to appear
```

### Connection refused?

Check if services are running:

```bash
# Qdrant
curl http://localhost:6333/health

# Ollama
curl http://localhost:11434/api/tags
```

### Need different embedding model?

```bash
# List available models
ollama list

# Pull a different one
ollama pull mxbai-embed-large  # Higher quality, larger
ollama pull all-minilm         # Smaller, faster

# Update environment variable
export OLLAMA_MODEL=mxbai-embed-large
```

## Next Steps

- See [README.md](README.md) for full documentation
- Check tool examples in README
- Run `uv run mcp dev server.py` to explore tools interactively
