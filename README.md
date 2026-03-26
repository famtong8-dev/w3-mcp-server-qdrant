# W3 MCP Qdrant Server

Python MCP server for vector search using [Qdrant](https://qdrant.tech/) vector database and [Ollama](https://ollama.ai/) embeddings.

**Status:** ✅ Working with Qdrant vector search and Ollama embeddings

## Features

- **qdrant_search** - Search for similar documents using text queries (auto-embedded via Ollama)
- **qdrant_list_collections** - List and manage Qdrant collections

Supports flexible output formats (Markdown or JSON) with configurable similarity thresholds.

## Quick Start

### 1. Prerequisites Setup

#### Qdrant Server

```bash
# Using Docker (Recommended)
docker run -p 6333:6333 qdrant/qdrant:latest
```

Or install locally: [Qdrant Quick Start](https://qdrant.tech/documentation/quick-start/)

#### Ollama Server

```bash
# Install: https://ollama.ai
ollama pull nomic-embed-text
ollama serve
```

Available embedding models:

- `nomic-embed-text` (768 dims) - recommended, lightweight
- `mxbai-embed-large` (1024 dims) - higher quality
- `all-minilm` (384 dims) - ultra-lightweight

### 2. Clean Setup (Important!)

```bash
cd /path/to/w3-mcp-server-qdrant

# Remove old lockfile and venv
rm -rf uv.lock .venv venv

# Unset old environment variable
unset VIRTUAL_ENV
```

### 3. Install Dependencies

```bash
# Install Python dependencies (using uv)
uv sync

# Install MCP CLI dependencies
uv pip install 'mcp[cli]'
```

### 4. Configure Environment

Create a `.env` file or export environment variables:

```bash
# Qdrant
export QDRANT_URL=http://localhost:6333
export QDRANT_API_KEY=  # Optional if using API key auth

# Ollama
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=nomic-embed-text
```

### 5. Verify Installation

```bash
# Check Qdrant
curl http://localhost:6333/health

# Check Ollama
curl http://localhost:11434/api/tags

# Check Python env
uv run python -c "from mcp.server.fastmcp import FastMCP; print('✓ MCP ready')"
```

### 6. Test with MCP Inspector

```bash
# Start MCP Inspector (interactive web UI)
uv run mcp dev server.py
```

Opens URL like:

```text
http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=...
```

Features:

- ✅ Available tools listed in sidebar
- ✅ Test each tool interactively with JSON input
- ✅ Real-time request/response viewing
- ✅ Server logs and debugging
- ✅ No extra dependencies needed

## Usage

### Option A: MCP Inspector (Development)

Best way to test and debug:

```bash
cd /path/to/w3-mcp-server-qdrant

# Start inspector
uv run mcp dev server.py
```

Opens web UI at `http://localhost:5173`:

- See available tools
- Test each tool with JSON input
- View request/response in real-time
- See server logs

### Option B: Direct Python

```bash
# Run server (stdio mode)
uv run python server.py
```

### Option C: Claude Code Integration

#### Method 1: From PyPI (Recommended)

Install from PyPI:

```bash
pip install w3-mcp-server-qdrant
# or
uv pip install w3-mcp-server-qdrant
```

Edit `~/.claude/claude_config.json` or `~/.mcp.json`:

```json
{
  "mcpServers": {
    "qdrant": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--with", "w3-mcp-server-qdrant", "w3-mcp-server-qdrant"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

**Advantages:**

- ✅ No need to clone the repo
- ✅ Easy version management
- ✅ Automatic dependency isolation

#### Method 2: From Local Source

Edit `~/.claude/claude_config.json`:

```json
{
  "mcpServers": {
    "qdrant": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "server.py"],
      "cwd": "/path/to/w3-mcp-server-qdrant",
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

Then restart Claude Code.

## Tools Documentation

### qdrant_search

Search for similar documents in a collection using text query (auto-embedded via Ollama).

**Parameters:**

- `collection_name` (string, required): Name of the collection to search
- `query_text` (string, required): Text to search for (will be embedded automatically)
- `limit` (integer, 1-100): Max results to return (default: 5)
- `score_threshold` (float, 0.0-1.0): Minimum similarity threshold (default: 0.0)
- `response_format` (string): "markdown" or "json" (default: "markdown")

**Example:**

```json
{
  "collection_name": "tech_docs",
  "query_text": "How do vector databases work?",
  "limit": 10,
  "score_threshold": 0.6,
  "response_format": "markdown"
}
```

**Output:**

Returns matching documents with similarity scores:

```markdown
Found 3 results for "How do vector databases work?":

1. [tech_docs.pdf:42](0.89) - Vector databases store embeddings...
2. [tutorial.md:15](0.76) - Getting started with vectors...
3. [paper.pdf:8](0.71) - Advanced vector indexing techniques...
```

---

### qdrant_list_collections

List all collections in Qdrant with metadata.

**Parameters:**

- `response_format` (string): "markdown" or "json" (default: "markdown")

**Example:**

```json
{
  "response_format": "json"
}
```

**Output:**

```json
{
  "collections": [
    {
      "name": "tech_docs",
      "points_count": 1250,
      "vector_size": 768
    },
    {
      "name": "papers",
      "points_count": 3840,
      "vector_size": 1024
    }
  ]
}
```

## Configuration

### QDRANT_URL

Specifies the URL of your Qdrant server.

**Set via:**

1. **Environment variable:**

   ```bash
   export QDRANT_URL=http://localhost:6333
   uv run python server.py
   ```

2. **.env file:**

   ```bash
   QDRANT_URL=http://localhost:6333
   ```

3. **In claude_config.json:**

   ```json
   "env": {
     "QDRANT_URL": "http://localhost:6333"
   }
   ```

### OLLAMA_BASE_URL

Specifies the URL of your Ollama server.

**Default:** `http://localhost:11434`

### OLLAMA_MODEL

Specifies which embedding model to use.

**Default:** `nomic-embed-text`

**Recommended models:**

- `nomic-embed-text` (768 dims) - balanced, good for most use cases
- `all-minilm` (384 dims) - fast, lightweight
- `mxbai-embed-large` (1024 dims) - higher quality, slower

## Project Structure

```text
w3-mcp-server-qdrant/
├── server.py              # MCP server entry point
├── pyproject.toml         # Project config
├── .env.example           # Environment variables template
├── README.md              # This file
└── tests/
    └── test_mcp_server.py # Integration tests
```

## How It Works

### Architecture

```text
MCP Client (Claude, IDE, etc.)
    ↓
MCP Server (server.py)
    ├── Ollama: text → embedding vector
    └── Qdrant: vector search
```

### Search Flow

1. **User provides text query**
2. **Ollama embeds query** → embedding vector
3. **Qdrant searches** for similar vectors
4. **Results returned** with scores and metadata

## Examples

### Search documents

```python
# Via Claude/MCP interface
qdrant_search(
    collection_name="tech_docs",
    query_text="machine learning algorithms",
    limit=5,
    score_threshold=0.6,
    response_format="markdown"
)
```

### List collections

```python
# Via Claude/MCP interface
qdrant_list_collections(response_format="json")
```

## Development

### Run tests

```bash
pytest tests/
```

### Code formatting

```bash
black server.py
ruff check server.py
```

### Testing with MCP Inspector

```bash
uv run mcp dev server.py
```

Web UI at `http://localhost:5173` shows:

- Available tools and schemas
- Real-time request/response
- Server logs
- Interactive testing

## Performance Tips

- **Score threshold**: Use `score_threshold` to filter low-relevance results and reduce noise
- **Result limit**: Adjust `limit` parameter (1-100) to balance quality vs. speed
- **Embedding model**: Choose based on quality vs. speed tradeoff:
  - `nomic-embed-text`: balanced (recommended)
  - `all-minilm`: fast, lightweight
  - `mxbai-embed-large`: higher quality but slower

## Troubleshooting

### Qdrant connection error

```bash
# Check if Qdrant is running
curl http://localhost:6333/health

# Start Qdrant with Docker
docker run -p 6333:6333 qdrant/qdrant:latest
```

### Ollama embedding failed

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Pull embedding model
ollama pull nomic-embed-text

# Start Ollama
ollama serve
```

### Collection not found

- Ensure collection exists in Qdrant
- Create collection through Qdrant UI or external tools
- Verify collection name matches exactly

### MCP module not found

```bash
# Install dependencies
uv sync

# Or manually
pip install mcp pydantic qdrant-client
```

### Server hangs on startup

- Check if Qdrant server is running and accessible
- Check if Ollama server is running
- Try: `curl http://localhost:6333/health` and `curl http://localhost:11434/api/tags`

## Future Enhancements

- [ ] Support for additional embedding models
- [ ] Batch vector operations
- [ ] Collection creation/deletion tools
- [ ] Vector update and delete operations
- [ ] Semantic search filters

## References

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Ollama](https://ollama.ai/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP](https://github.com/anthropics/mcp-fastmcp)

## License

MIT
