# Release Guide

Instructions for building, testing, and publishing the `w3-mcp-server-qdrant` package.

## Table of Contents

- [Local Installation](#local-installation)
- [Building](#building)
- [Publishing to PyPI](#publishing-to-pypi)
- [Using with UV](#using-with-uv)
- [Version Management](#version-management)

## Local Installation

### Development Install

For development, install in editable mode:

```bash
pip install -e .
```

This installs the package with all dependencies and creates the CLI entry point `w3-mcp-server-qdrant`.

### Installation with Optional Dependencies

Install with development tools:

```bash
pip install -e ".[dev]"
```

This includes:
- pytest
- pytest-asyncio
- black (code formatter)
- ruff (linter)

## Building

### Prerequisites

Install build tools:

```bash
pip install build twine
```

### Build Package

Create distribution files (wheel and source tarball):

```bash
python -m build
```

This generates:
- `dist/w3_mcp_server_qdrant-0.1.0.tar.gz` - Source distribution
- `dist/w3_mcp_server_qdrant-0.1.0-py3-none-any.whl` - Wheel distribution

### Verify Build

```bash
twine check dist/*
```

## Publishing to PyPI

### 1. Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Create your account
3. Verify your email

### 2. Create API Token

1. Go to https://pypi.org/manage/account/token/
2. Create a new token with "Entire repository" scope
3. Copy the token (format: `pypi-AgEIc...`)

### 3. Configure Authentication

**Option A: Store token in `.pypirc`**

Create `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIc...
```

**Option B: Use environment variable**

```bash
export TWINE_PASSWORD="pypi-AgEIc..."
export TWINE_USERNAME="__token__"
```

### 4. Upload to PyPI

```bash
# Using .pypirc
python -m twine upload dist/*

# Or with explicit credentials
python -m twine upload -u __token__ -p pypi-AgEIc... dist/*
```

### 5. Verify Publication

Check that the package appears on PyPI:

https://pypi.org/project/w3-mcp-server-qdrant/

## Using with UV

### Installation

Once published to PyPI:

```bash
# Add to project dependencies
uv add w3-mcp-server-qdrant

# Or install globally
uv tool install w3-mcp-server-qdrant
```

### Running the Server

```bash
# Direct command
w3-mcp-server-qdrant

# Or with uv
uv run w3-mcp-server-qdrant
```

### Configuration for Claude Desktop

Add to `~/.claude/mcp_servers.json`:

```json
{
  "mcpServers": {
    "qdrant": {
      "command": "w3-mcp-server-qdrant",
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

Restart Claude Desktop and the server will be available.

## Version Management

### Update Version

Edit `pyproject.toml`:

```toml
[project]
version = "0.2.0"  # Update this
```

### Release Process

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG** (if exists)
3. **Test locally**:
   ```bash
   pip install -e .
   w3-mcp-server-qdrant
   ```
4. **Build distribution**:
   ```bash
   python -m build
   ```
5. **Verify with twine**:
   ```bash
   twine check dist/*
   ```
6. **Create git tag** (optional):
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
7. **Upload to PyPI**:
   ```bash
   python -m twine upload dist/*
   ```

## Troubleshooting

### Build errors

```bash
# Clean build artifacts
rm -rf build dist *.egg-info

# Rebuild
python -m build
```

### Upload authentication fails

```bash
# Verify token
echo $TWINE_PASSWORD

# Check .pypirc permissions
chmod 600 ~/.pypirc

# Try with explicit credentials
python -m twine upload -u __token__ -p your-token-here dist/*
```

### Package not found after upload

PyPI caches for ~15 minutes. Wait and try again:

```bash
pip install --upgrade w3-mcp-server-qdrant
```

## Additional Resources

- [PyPI Help](https://pypi.org/help/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Python Packaging Guide](https://packaging.python.org/)
- [PEP 427 - Wheel Binary Format](https://www.python.org/dev/peps/pep-0427/)
