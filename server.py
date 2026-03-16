#!/usr/bin/env python3
"""MCP server for vector search with Qdrant and Ollama embeddings."""

import json
import os
from enum import Enum
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, field_validator, ConfigDict
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse

# Configuration from environment variables
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "nomic-embed-text")

# HTTP client for Ollama
http_client = httpx.AsyncClient(timeout=60.0)


async def embed_text(text: str) -> list[float]:
    """Generate embedding using Ollama."""
    try:
        response = await http_client.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={
                "model": OLLAMA_MODEL,
                "input": text,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0] if data.get("embeddings") else []
    except httpx.HTTPError as e:
        raise ValueError(f"Failed to embed text with Ollama: {e}")


@asynccontextmanager
async def app_lifespan(app):
    """Manage Qdrant client lifecycle."""
    client = AsyncQdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
    )
    yield {"qdrant": client}
    await client.close()


mcp = FastMCP("qdrant_mcp", lifespan=app_lifespan)


class ResponseFormat(str, Enum):
    """Output format options."""
    MARKDOWN = "markdown"
    JSON = "json"


class SearchInput(BaseModel):
    """Input for vector search."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    collection_name: str = Field(
        ...,
        description="Qdrant collection name to search in",
        min_length=1,
        max_length=255,
    )
    query_text: str = Field(
        ...,
        description="Text to embed and search for similar documents",
        min_length=1,
        max_length=10000,
    )
    limit: int = Field(
        default=5,
        description="Maximum number of results to return",
        ge=1,
        le=100,
    )
    score_threshold: Optional[float] = Field(
        default=0.0,
        description="Minimum similarity score (0.0-1.0). Default 0.0 returns all results.",
        ge=0.0,
        le=1.0,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )

    @field_validator("collection_name")
    @classmethod
    def validate_collection(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Collection name cannot be empty")
        return v.strip()

    @field_validator("query_text")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query text cannot be empty")
        return v.strip()


class UpsertInput(BaseModel):
    """Input for upserting documents with auto-embedding."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    collection_name: str = Field(
        ...,
        description="Qdrant collection name",
        min_length=1,
        max_length=255,
    )
    document_id: int = Field(
        ...,
        description="Unique document ID (integer)",
        gt=0,
    )
    text: str = Field(
        ...,
        description="Document text to embed and store",
        min_length=1,
        max_length=50000,
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Optional metadata to store with the document (JSON object)",
    )

    @field_validator("collection_name")
    @classmethod
    def validate_collection(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Collection name cannot be empty")
        return v.strip()


class ListCollectionsInput(BaseModel):
    """Input for listing collections."""
    model_config = ConfigDict(extra="forbid")

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


@mcp.tool(
    name="qdrant_search",
    annotations={
        "title": "Search Vector Database",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def qdrant_search(params: SearchInput, ctx: Context) -> str:
    """Search for similar documents in Qdrant.

    Embeds the query text using Ollama, then searches for similar vectors
    in the specified Qdrant collection. Returns matching documents with
    similarity scores.

    Args:
        params (SearchInput): Validated parameters:
            - collection_name (str): Collection to search in
            - query_text (str): Text to search for (auto-embedded)
            - limit (int): Max results, 1-100 (default: 5)
            - score_threshold (float): Min similarity 0.0-1.0 (default: 0.0)
            - response_format (str): 'markdown' or 'json'

    Returns:
        str: Formatted search results with document IDs, texts, and scores

    Examples:
        - Search: query_text="machine learning algorithms"
        - Filter: score_threshold=0.5 (exclude low-relevance results)

    Errors:
        - Collection not found: "Collection 'xyz' does not exist"
        - Embedding failed: "Failed to embed query text"
        - Connection error: "Cannot connect to Qdrant at {url}"
    """
    try:
        await ctx.info(f"Embedding query: {params.query_text[:50]}...")
        query_vector = await embed_text(params.query_text)

        if not query_vector:
            return json.dumps({
                "error": "Failed to generate embedding for query text",
                "query": params.query_text,
            })

        qdrant: AsyncQdrantClient = ctx.request_context.lifespan_context["qdrant"]

        await ctx.info(f"Searching in collection: {params.collection_name}")
        result = await qdrant.query_points(
            collection_name=params.collection_name,
            query=query_vector,
            limit=params.limit,
            score_threshold=params.score_threshold,
        )
        results = result.points

        # Format results
        matches = []
        for result in results:
            match = {
                "document_id": result.id,
                "score": result.score,
                "metadata": result.payload,
            }
            matches.append(match)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "query": params.query_text,
                "collection": params.collection_name,
                "count": len(matches),
                "matches": matches,
            }, indent=2)
        else:
            # Markdown format
            md = f"# Search Results\n\n"
            md += f"**Query**: {params.query_text}\n"
            md += f"**Collection**: {params.collection_name}\n"
            md += f"**Results**: {len(matches)} found\n\n"

            if not matches:
                md += "No documents found."
            else:
                for i, match in enumerate(matches, 1):
                    md += f"## Result {i}\n"
                    md += f"- **ID**: {match['document_id']}\n"
                    md += f"- **Similarity**: {match['score']:.4f}\n"
                    if match["metadata"]:
                        md += f"- **Metadata**: `{json.dumps(match['metadata'])}`\n"
                    md += "\n"

            return md

    except UnexpectedResponse as e:
        if "not found" in str(e).lower():
            return json.dumps({
                "error": f"Collection '{params.collection_name}' does not exist"
            })
        return json.dumps({
            "error": f"Qdrant error: {str(e)}"
        })
    except Exception as e:
        await ctx.error(f"Search failed: {type(e).__name__}: {e}")
        return json.dumps({
            "error": f"Search failed: {str(e)}"
        })


@mcp.tool(
    name="qdrant_upsert",
    annotations={
        "title": "Store Document with Auto-Embedding",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def qdrant_upsert(params: UpsertInput, ctx: Context) -> str:
    """Store or update a document with automatic Ollama embedding.

    Embeds the provided text using Ollama, then upserts (creates or updates)
    the document in the specified Qdrant collection. Metadata is optional.

    Args:
        params (UpsertInput): Validated parameters:
            - collection_name (str): Target collection
            - document_id (int): Unique document ID
            - text (str): Document text (will be embedded)
            - metadata (dict, optional): Additional data to store

    Returns:
        str: Success confirmation or error message

    Examples:
        - Store document: text="This is a sample document", metadata={"title": "Sample"}
        - Update existing: document_id=123 (same ID overwrites previous)

    Errors:
        - Collection not found: "Collection 'xyz' does not exist"
        - Invalid ID: "Document ID must be a positive integer"
        - Embedding failed: "Failed to embed document text"
        - Connection error: "Cannot connect to Qdrant at {url}"
    """
    try:
        await ctx.info(f"Embedding document {params.document_id}...")
        embedding = await embed_text(params.text)

        if not embedding:
            return json.dumps({
                "error": "Failed to generate embedding for document",
                "document_id": params.document_id,
            })

        qdrant: AsyncQdrantClient = ctx.request_context.lifespan_context["qdrant"]

        # Prepare payload
        payload = params.metadata or {}
        payload["text"] = params.text

        await ctx.info(f"Upserting to collection: {params.collection_name}")

        # Upsert point (works with or without collection existing)
        await qdrant.upsert(
            collection_name=params.collection_name,
            points=[
                PointStruct(
                    id=params.document_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )

        return json.dumps({
            "success": True,
            "message": f"Document {params.document_id} stored successfully",
            "collection": params.collection_name,
            "embedding_model": OLLAMA_MODEL,
            "embedding_size": len(embedding),
        }, indent=2)

    except UnexpectedResponse as e:
        return json.dumps({
            "error": f"Qdrant error: {str(e)}"
        })
    except Exception as e:
        await ctx.error(f"Upsert failed: {type(e).__name__}: {e}")
        return json.dumps({
            "error": f"Upsert failed: {str(e)}"
        })


@mcp.tool(
    name="qdrant_list_collections",
    annotations={
        "title": "List Qdrant Collections",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def qdrant_list_collections(params: ListCollectionsInput, ctx: Context) -> str:
    """List all collections in Qdrant.

    Retrieves metadata about all collections including point counts and
    vector dimensions.

    Args:
        params (ListCollectionsInput): Validated parameters:
            - response_format (str): 'markdown' or 'json'

    Returns:
        str: Formatted list of collections with metadata

    Errors:
        - Connection error: "Cannot connect to Qdrant at {url}"
    """
    try:
        qdrant: AsyncQdrantClient = ctx.request_context.lifespan_context["qdrant"]

        await ctx.info("Fetching collections from Qdrant...")
        collections = await qdrant.get_collections()

        collection_list = []
        for collection in collections.collections:
            coll_info = {
                "name": collection.name,
                "points_count": 0,
                "vectors_count": 0,
                "vector_size": "?",
            }
            # Get detailed collection info
            try:
                config = await qdrant.get_collection(collection.name)
                if hasattr(config, 'points_count'):
                    coll_info["points_count"] = config.points_count or 0
                if hasattr(config, 'vectors_count'):
                    coll_info["vectors_count"] = config.vectors_count or 0

                # Get vector size from config
                if hasattr(config, 'config') and config.config and hasattr(config.config, 'params'):
                    if hasattr(config.config.params, 'vectors') and config.config.params.vectors:
                        if isinstance(config.config.params.vectors, dict):
                            for v in config.config.params.vectors.values():
                                if hasattr(v, 'size'):
                                    coll_info["vector_size"] = v.size
                                    break
                        elif hasattr(config.config.params.vectors, 'size'):
                            coll_info["vector_size"] = config.config.params.vectors.size
            except Exception:
                pass

            collection_list.append(coll_info)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "total": len(collection_list),
                "collections": collection_list,
            }, indent=2)
        else:
            # Markdown format
            md = f"# Qdrant Collections\n\n"
            md += f"Total collections: {len(collection_list)}\n\n"

            if not collection_list:
                md += "No collections found."
            else:
                md += "| Collection | Points | Vectors | Vector Size |\n"
                md += "|---|---|---|---|\n"
                for c in collection_list:
                    vector_size = c.get("vector_size", "?")
                    md += f"| {c['name']} | {c['points_count']} | {c['vectors_count']} | {vector_size} |\n"

            return md

    except Exception as e:
        await ctx.error(f"Failed to list collections: {type(e).__name__}: {e}")
        return json.dumps({
            "error": f"Failed to list collections: {str(e)}"
        })


if __name__ == "__main__":
    mcp.run()
