# W3 MCP Qdrant Server

Python MCP server for vector search using [Qdrant](https://qdrant.tech/) vector database and [Ollama](https://ollama.ai/) embeddings.

**Status:** ✅ Working with Qdrant vector search and Ollama embeddings + Advanced query techniques

## Features

- **qdrant_search** - Search for similar documents using text queries (auto-embedded via Ollama)
  - ✨ Query Expansion - Generate N query variations, search all, merge with RRF
  - ✨ HyDE - Hypothetical Document Embeddings for semantic enrichment
  - ✨ Reranking - Use LLM to reorder results by relevance
- **qdrant_list_collections** - List and manage Qdrant collections

Supports flexible output formats (Markdown or JSON) with configurable similarity thresholds and advanced search options.

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
ollama pull bge-m3
ollama pull mistral
ollama serve
```

Available embedding models:

- `bge-m3` (384 dims) - ⭐ **recommended** - best quality-speed balance
- `nomic-embed-text` (768 dims) - balanced, good for general use
- `mxbai-embed-large` (1024 dims) - highest quality
- `all-minilm` (384 dims) - ultra-lightweight, good for mobile

### 2. Clean Setup (Important!)

```bash
cd /path/to/w3-mcp-server-qdrant

# Remove old lockfile and venv
rm -rf uv.lock .venv venv

# Unset old environment variable
unset VIRTUAL_ENV
```

### 3. Install Dependencies with uv

```bash
# Install all Python dependencies using uv
uv sync
```

That's it! `uv sync` installs all dependencies including MCP, pydantic, qdrant-client, and httpx.

### 4. Configure Environment

Create a `.env` file from template:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # Optional if using API key auth

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=bge-m3:latest
OLLAMA_RERANK_MODEL=mistral  # For query expansion and reranking
```

Or export environment variables:

```bash
export QDRANT_URL=http://localhost:6333
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_EMBED_MODEL=bge-m3:latest
export OLLAMA_RERANK_MODEL=mistral
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

#### Method 1: Local Source (Development)

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
        "OLLAMA_EMBED_MODEL": "bge-m3:latest",
        "OLLAMA_RERANK_MODEL": "mistral"
      }
    }
  }
}
```

**Advantages:**

- ✅ Run latest development version
- ✅ Easy to modify and test changes
- ✅ Direct access to source code

#### Method 2: PyPI Installation (When Published)

Install from PyPI (always fetch latest version):

```bash
uv run --with w3-mcp-server-qdrant --refresh w3-mcp-server-qdrant
```

Edit `~/.claude/claude_config.json`:

```json
{
  "mcpServers": {
    "qdrant": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--with", "w3-mcp-server-qdrant", "--refresh", "w3-mcp-server-qdrant"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_EMBED_MODEL": "bge-m3:latest",
        "OLLAMA_RERANK_MODEL": "mistral"
      }
    }
  }
}
```

**Advantages:**

- ✅ No need to clone repository
- ✅ Easy version management
- ✅ Automatic dependency isolation

Then restart Claude Code.

## Tools Documentation

### qdrant_search

Search for similar documents in a collection using text query (auto-embedded via Ollama).

Supports advanced search techniques: query expansion, hypothetical document embeddings (HyDE), and LLM-based reranking.

#### Basic Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `collection_name` | string | required | Name of the collection to search |
| `query_text` | string | required | Text to search for (auto-embedded via Ollama) |
| `limit` | integer | 5 | Max results to return (1-100) |
| `score_threshold` | float | 0.0 | Minimum similarity threshold (0.0-1.0) |
| `fields` | string | "" | Comma-separated metadata fields to return (empty = all) |
| `response_format` | string | "markdown" | "markdown" or "json" |

#### Advanced Parameters - Query Expansion

Generate N query variations, search all in parallel, merge results with Reciprocal Rank Fusion:

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `expand_query` | boolean | false | Enable query expansion |
| `expand_query_count` | integer | 3 | Number of variations to generate (1-10) |

#### Advanced Parameters - HyDE

Generate a hypothetical document matching the query intent, then embed it:

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `use_hyde` | boolean | false | Enable HyDE |
| `hyde_combine_original` | boolean | true | Also search original query + HyDE doc |

#### Advanced Parameters - Reranking

Use LLM to reorder results by relevance to the original query:

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `rerank` | boolean | false | Enable LLM reranking |
| `rerank_top_n` | integer | 10 | Number of results to rerank (1-100) |

#### Examples

**Example 1: Basic search**

```json
{
  "collection_name": "docs",
  "query_text": "machine learning",
  "limit": 5
}
```

**Example 2: Query expansion (good recall)**

```json
{
  "collection_name": "docs",
  "query_text": "machine learning",
  "expand_query": true,
  "expand_query_count": 5,
  "limit": 5
}
```

**Example 3: HyDE (semantic understanding)**

```json
{
  "collection_name": "docs",
  "query_text": "machine learning",
  "use_hyde": true,
  "hyde_combine_original": true,
  "limit": 5
}
```

**Example 4: Full combo (best quality, slower)**

```json
{
  "collection_name": "docs",
  "query_text": "machine learning",
  "expand_query": true,
  "expand_query_count": 3,
  "use_hyde": true,
  "rerank": true,
  "rerank_top_n": 15,
  "limit": 5
}
```

#### Output Format

Returns JSON with search metadata and ranked results:

```json
{
  "query": "machine learning",
  "collection": "docs",
  "total": 3,
  "search_method": "rrf+hyde+expand+rerank",
  "results": [
    {
      "index": 1,
      "id": "doc_123",
      "score": 0.0273,
      "metadata": {
        "title": "Machine Learning Basics",
        "author": "Jane Doe"
      }
    }
  ]
}
```

**Note:** `search_method` field indicates which techniques were applied:
- `basic` - simple vector search
- `rrf` - multiple searches merged with Reciprocal Rank Fusion
- `rrf+hyde` - RRF with HyDE
- `rrf+expand` - RRF with query expansion
- `rrf+hyde+expand+rerank` - all techniques combined

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

### OLLAMA_EMBED_MODEL

Specifies which embedding model to use for embedding search queries and documents.

**Default:** `bge-m3:latest`

**Recommended embedding models:**

- `bge-m3` (384 dims) - ⭐ **Recommended** - best quality-to-speed ratio
- `nomic-embed-text` (768 dims) - balanced, good for most use cases
- `all-minilm` (384 dims) - fast, lightweight
- `mxbai-embed-large` (1024 dims) - highest quality but slower

### OLLAMA_RERANK_MODEL

Specifies which LLM model to use for advanced features (query expansion, HyDE, reranking).

**Default:** `mistral`

**Recommended models:**

- `mistral` (7B) - ⭐ Recommended - good quality, reasonable speed
- `qwen2.5-coder` (7B) - high quality but optimized for code
- `llama3.2` (3B) - smaller, faster but lower quality
- `neural-chat` (7B) - good for instruction-following

**Note:** Only used when `expand_query=true`, `use_hyde=true`, or `rerank=true`

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

### Run tests using uv

```bash
uv run pytest tests/
```

### Code formatting with uv

```bash
uv run black server.py
uv run ruff check server.py
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

### Basic Search Optimization

- **Score threshold**: Use `score_threshold` to filter low-relevance results and reduce noise
- **Result limit**: Adjust `limit` parameter (1-100) to balance quality vs. speed
- **Embedding model**: Choose based on quality vs. speed tradeoff:
  - `nomic-embed-text`: balanced (recommended)
  - `all-minilm`: fast, lightweight
  - `mxbai-embed-large`: higher quality but slower

### Advanced Features Trade-offs

| Feature | Quality | Speed | Use Case |
| --- | --- | --- | --- |
| Basic search | ⭐⭐ | ⚡⚡⚡ | Clear, specific queries |
| Query expansion | ⭐⭐⭐ | ⚡⚡ | Ambiguous queries, high recall needed |
| HyDE | ⭐⭐⭐ | ⚡⚡ | Semantic understanding important |
| Reranking | ⭐⭐⭐⭐ | ⚡ | Precision critical, can wait 1-2s |
| All combined | ⭐⭐⭐⭐⭐ | ⚡ | Best quality, time not critical |

### Performance Strategy

- **Fast path**: Basic search with `limit=5`
- **Balanced**: `expand_query=true, expand_query_count=3`
- **High quality**: Add `use_hyde=true`
- **Maximum quality**: Add `rerank=true` (slowest, ~5-10s)

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
# Install dependencies with uv
uv sync
```

### Server hangs on startup

- Check if Qdrant server is running and accessible
- Check if Ollama server is running
- Try: `curl http://localhost:6333/health` and `curl http://localhost:11434/api/tags`

## Implemented Features

- [x] Query expansion with LLM-generated variations
- [x] HyDE (Hypothetical Document Embeddings)
- [x] Reciprocal Rank Fusion (RRF) for result merging
- [x] LLM-based result reranking
- [x] Parallel async embedding and search

## Future Enhancements

- [ ] Support for additional embedding models
- [ ] Batch vector operations
- [ ] Collection creation/deletion tools
- [ ] Vector update and delete operations
- [ ] Semantic search filters
- [ ] Caching for query expansions
- [ ] Custom RRF weights configuration

## References

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Ollama](https://ollama.ai/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP](https://github.com/anthropics/mcp-fastmcp)

## License

MIT
