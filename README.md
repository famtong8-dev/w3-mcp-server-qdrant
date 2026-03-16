# Qdrant MCP Server

Model Context Protocol server for vector search using [Qdrant](https://qdrant.tech/) and [Ollama](https://ollama.ai/) embeddings.

## Features

- **Vector Search**: Search for similar documents using text queries (auto-embedded via Ollama)
- **Auto-Embedding**: Automatically embed text using Ollama before storage
- **Collection Management**: List and manage Qdrant collections
- **Metadata Support**: Store custom metadata with documents
- **Flexible Output**: Markdown or JSON response formats

## Prerequisites

### Qdrant Server

```bash
docker run -p 6333:6333 qdrant/qdrant:latest
```

Or install locally: [Qdrant Quick Start](https://qdrant.tech/documentation/quick-start/)

### Ollama Server

```bash
# Install: https://ollama.ai
ollama pull nomic-embed-text
ollama serve
```

Other embedding models available:

- `nomic-embed-text` (768 dims) - recommended, lightweight
- `mxbai-embed-large` (1024 dims) - higher quality
- `all-minilm` (384 dims) - ultra-lightweight

## Installation

```bash
# Clone/navigate to project directory
cd w3-mcp-server-qdrant

# Install dependencies
pip install -e .

# Or with uv:
uv sync
```

## Configuration

Create a `.env` file or export environment variables:

```bash
# Qdrant
export QDRANT_URL=http://localhost:6333
export QDRANT_API_KEY=  # Optional if using API key auth

# Ollama
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=nomic-embed-text
```

## Usage

### Run with stdio transport

```bash
python server.py
```

### Test with MCP Inspector

```bash
uv run mcp dev server.py
```

Then open http://localhost:5173 in your browser.

### Configure in Claude Desktop

Add to `~/.claude/mcp_servers.json`:

```json
{
  "mcpServers": {
    "qdrant": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

## Tools

### qdrant_search

Search for similar documents in a collection.

**Parameters:**
- `collection_name` (string): Name of the collection to search
- `query_text` (string): Text to search for (will be embedded)
- `limit` (integer, 1-100): Max results (default: 5)
- `score_threshold` (float, 0.0-1.0): Min similarity threshold (default: 0.0)
- `response_format` (string): "markdown" or "json" (default: markdown)

**Example:**
```
Search documents about "machine learning" in the "papers" collection
with a similarity threshold of 0.7, return top 10 results as JSON
```

### qdrant_upsert

Store or update a document with automatic embedding.

**Parameters:**
- `collection_name` (string): Target collection name
- `document_id` (integer): Unique document ID
- `text` (string): Document text to embed and store
- `metadata` (object, optional): Additional metadata

**Example:**
```
Store the document "The history of AI" with ID 42 in the "papers"
collection with metadata {"author": "John Doe", "year": 2024}
```

### qdrant_list_collections

List all collections in Qdrant with metadata.

**Parameters:**
- `response_format` (string): "markdown" or "json" (default: markdown)

## Examples

### Store documents

```python
# Via Claude/MCP interface
qdrant_upsert(
    collection_name="tech_docs",
    document_id=1,
    text="Vector databases enable fast similarity search on high-dimensional data",
    metadata={"category": "databases", "source": "article"}
)
```

### Search documents

```python
# Via Claude/MCP interface
qdrant_search(
    collection_name="tech_docs",
    query_text="How do vector databases work?",
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

## Architecture

```
Claude/LLM
    ↓
MCP Server (server.py)
    ├── Ollama: text → embedding
    └── Qdrant: search/store vectors
```

### Data Flow

**Search**:
1. User provides text query
2. Ollama embeds the query → vector
3. Qdrant searches for similar vectors
4. Results returned with scores and metadata

**Upsert**:
1. User provides text + document ID + optional metadata
2. Ollama embeds the text → vector
3. Qdrant stores the point (vector + payload)

## Error Handling

- **Collection not found**: Ensure collection exists in Qdrant
- **Connection error**: Verify Qdrant/Ollama servers are running
- **Embedding failed**: Check Ollama model is loaded (`ollama pull nomic-embed-text`)

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

## Performance Tips

- **Batch operations**: Store multiple documents efficiently with upsert
- **Score threshold**: Use `score_threshold` to filter low-relevance results
- **Embedding model**: Choose based on quality vs. speed tradeoff:
  - `nomic-embed-text`: balanced (recommended)
  - `all-minilm`: fast, lightweight
  - `mxbai-embed-large`: higher quality but slower

## Troubleshooting

**Issue**: "Cannot connect to Qdrant"
- Check: `curl http://localhost:6333/health`
- Start Qdrant: `docker run -p 6333:6333 qdrant/qdrant:latest`

**Issue**: "Failed to embed text"
- Check: `curl http://localhost:11434/api/tags`
- Pull model: `ollama pull nomic-embed-text`
- Start Ollama: `ollama serve`

**Issue**: "Collection not found"
- Create collection: Use `qdrant_upsert` (auto-creates) or Qdrant console

## License

MIT
