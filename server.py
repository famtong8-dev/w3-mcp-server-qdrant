#!/usr/bin/env python3
"""MCP server for vector search with Qdrant and Ollama embeddings."""

import json
import os
import asyncio
from enum import Enum
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, field_validator, ConfigDict
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

# Configuration from environment variables
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "bge-m3:latest")
OLLAMA_RERANK_MODEL = os.environ.get("OLLAMA_RERANK_MODEL", "mistral")

# HTTP clients for Ollama
http_client = httpx.AsyncClient(timeout=60.0)
http_client_gen = httpx.AsyncClient(timeout=120.0)


async def embed_text(text: str) -> list[float]:
    """Generate embedding using Ollama."""
    try:
        response = await http_client.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={
                "model": OLLAMA_EMBED_MODEL,
                "input": text,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0] if data.get("embeddings") else []
    except httpx.HTTPError as e:
        raise ValueError(f"Failed to embed text with Ollama: {e}")


async def generate_text(prompt: str) -> str:
    """Generate text using Ollama /api/generate endpoint."""
    try:
        response = await http_client_gen.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_RERANK_MODEL,
                "prompt": prompt,
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise ValueError(f"Ollama generation error: {data['error']}")
        return data.get("response", "").strip()
    except httpx.HTTPError as e:
        raise ValueError(f"Failed to generate text with Ollama: {e}")


async def expand_query_variations(query: str, n: int) -> list[str]:
    """Generate n alternative phrasings of a query using the LLM."""
    try:
        prompt = f"""Generate {n} alternative search queries for the following query.
Return ONLY the queries, one per line, no numbering, no extra text.

Original query: {query}"""

        response = await generate_text(prompt)

        # Parse: split by newline, strip, filter empty
        lines = [line.strip() for line in response.split("\n") if line.strip()]

        # Deduplicate while preserving order
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)

        # Trim to at most n and return
        result = unique_lines[:n]
        return result if result else [query]
    except Exception:
        # Fallback: return original query if expansion fails
        return [query]


async def generate_hypothetical_document(query: str) -> str:
    """Generate a hypothetical document that would answer the query (HyDE)."""
    try:
        prompt = f"""Write a detailed paragraph that directly answers the following question.
Write as if you are a document that would be found by searching for this query.
Do not mention that you are a hypothetical document.

Query: {query}"""

        response = await generate_text(prompt)
        return response if response else query
    except Exception:
        # Fallback: return original query if generation fails
        return query


def reciprocal_rank_fusion(
    result_lists: list[list[dict]], k: int = 60
) -> list[dict]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion (RRF).

    Each result must have a 'document_id' key. Returns merged list sorted by
    RRF score in descending order.
    """
    if not result_lists:
        return []

    scores: dict = {}  # document_id -> accumulated RRF score
    payloads: dict = {}  # document_id -> full result dict

    # Accumulate RRF scores across all result lists
    for result_list in result_lists:
        for rank, item in enumerate(result_list, start=1):  # 1-based rank
            doc_id = item.get("document_id")
            if doc_id is None:
                continue

            # RRF formula: 1 / (k + rank)
            score_contribution = 1.0 / (k + rank)
            scores[doc_id] = scores.get(doc_id, 0.0) + score_contribution

            # Keep first occurrence of each document's full data
            if doc_id not in payloads:
                payloads[doc_id] = item.copy()

    # Sort by RRF score descending
    sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Rebuild merged list with RRF scores
    merged = []
    for doc_id, rrf_score in sorted_docs:
        item = payloads[doc_id].copy()
        item["score"] = rrf_score
        merged.append(item)

    return merged


async def rerank_results(
    query: str, candidates: list[dict], top_n: int
) -> list[dict]:
    """Use LLM to rerank candidates by relevance to the query.

    Returns a reordered list of up to top_n documents.
    """
    if not candidates:
        return candidates

    # Truncate to top_n
    truncated = candidates[:top_n]

    # Extract text snippets for each document
    snippets = []
    for i, doc in enumerate(truncated, start=1):
        # Try to find text field in metadata
        metadata = doc.get("metadata", {})
        text_value = None

        # Priority: look for 'text', 'content', 'page_content', or first string value
        for key in ["text", "content", "page_content"]:
            if key in metadata and isinstance(metadata[key], str):
                text_value = metadata[key]
                break

        if not text_value:
            # Find first string value in metadata
            for v in metadata.values():
                if isinstance(v, str):
                    text_value = v
                    break

        if not text_value:
            text_value = "(no text)"

        # Truncate to 300 chars
        snippet = text_value[:300] if text_value else "(no text)"
        snippets.append(f"{i}. {snippet}")

    numbered_snippets = "\n".join(snippets)

    prompt = f"""Rank the following documents by relevance to the query.
Return ONLY the document numbers in order from most to least relevant,
separated by commas (e.g., "3,1,4,2").

Query: {query}

Documents:
{numbered_snippets}"""

    try:
        response = await generate_text(prompt)

        # Parse comma-separated numbers
        numbers_str = response.strip()
        if not numbers_str:
            return truncated

        # Split and parse
        numbers = []
        for num_str in numbers_str.split(","):
            try:
                num = int(num_str.strip()) - 1  # Convert to 0-based index
                if 0 <= num < len(truncated):
                    numbers.append(num)
            except ValueError:
                pass

        if not numbers:
            return truncated

        # Remove duplicates while preserving order
        seen = set()
        unique_numbers = []
        for num in numbers:
            if num not in seen:
                seen.add(num)
                unique_numbers.append(num)

        # Reorder by LLM ranking
        reordered = [truncated[i] for i in unique_numbers]

        # Append any un-mentioned documents at the end
        mentioned = set(unique_numbers)
        for i, doc in enumerate(truncated):
            if i not in mentioned:
                reordered.append(doc)

        return reordered

    except Exception:
        # Fallback: return truncated list unchanged if reranking fails
        return truncated


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
    fields: str = Field(
        default="",
        description="Comma-separated metadata fields to return (e.g., 'title,author,date'). Leave empty to return all fields.",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )
    expand_query: bool = Field(
        default=False,
        description="If True, uses LLM to generate query variations and searches for each. Results are merged via Reciprocal Rank Fusion.",
    )
    expand_query_count: int = Field(
        default=3,
        description="Number of query variations to generate when expand_query=True.",
        ge=1,
        le=10,
    )
    use_hyde: bool = Field(
        default=False,
        description="If True, uses LLM to generate a hypothetical document matching the query, then embeds that document.",
    )
    hyde_combine_original: bool = Field(
        default=True,
        description="When use_hyde=True, also run a search on the original query embedding and merge via RRF.",
    )
    rerank: bool = Field(
        default=False,
        description="If True, uses LLM to rerank the merged results for relevance to the original query.",
    )
    rerank_top_n: int = Field(
        default=10,
        description="Number of top candidates to pass to the LLM reranker.",
        ge=1,
        le=100,
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

    Supports advanced features:
    - Query expansion: generates multiple query variations and merges results
    - HyDE: generates hypothetical documents for semantic enrichment
    - RRF: Reciprocal Rank Fusion for merging multiple result sets
    - Reranking: uses LLM to reorder results by relevance

    Args:
        params (SearchInput): Validated parameters:
            - collection_name (str): Collection to search in
            - query_text (str): Text to search for (auto-embedded)
            - limit (int): Max results, 1-100 (default: 5)
            - score_threshold (float): Min similarity 0.0-1.0 (default: 0.0)
            - fields (str): Comma-separated metadata fields to return (optional)
            - response_format (str): 'markdown' or 'json'
            - expand_query (bool): Enable query expansion (default: False)
            - expand_query_count (int): Number of variations (default: 3)
            - use_hyde (bool): Enable HyDE (default: False)
            - hyde_combine_original (bool): Include original query with HyDE (default: True)
            - rerank (bool): Enable LLM reranking (default: False)
            - rerank_top_n (int): Candidates for reranking (default: 10)

    Returns:
        str: Formatted search results with document IDs, texts, and scores

    Errors:
        - Collection not found: "Collection 'xyz' does not exist"
        - Embedding failed: "Failed to embed query text"
        - Connection error: "Cannot connect to Qdrant at {url}"
    """
    try:
        qdrant: AsyncQdrantClient = ctx.request_context.lifespan_context["qdrant"]

        # Step 1: Decide which query texts to embed
        texts_to_embed = []

        if params.use_hyde:
            await ctx.info("Generating hypothetical document...")
            hyde_doc = await generate_hypothetical_document(params.query_text)
            if params.hyde_combine_original:
                texts_to_embed = [params.query_text, hyde_doc]
            else:
                texts_to_embed = [hyde_doc]
        else:
            texts_to_embed = [params.query_text]

        if params.expand_query:
            await ctx.info(f"Expanding query into {params.expand_query_count} variations...")
            variations = await expand_query_variations(params.query_text, params.expand_query_count)
            texts_to_embed.extend(variations)

        # Step 2: Generate all embeddings in parallel
        await ctx.info(f"Embedding {len(texts_to_embed)} query variations...")
        vectors = await asyncio.gather(*[embed_text(t) for t in texts_to_embed])

        # Filter out empty vectors (failed embeddings)
        valid_pairs = [(t, v) for t, v in zip(texts_to_embed, vectors) if v]

        if not valid_pairs:
            return json.dumps({
                "error": "Failed to generate embeddings for all query texts",
                "query": params.query_text,
            })

        valid_vectors = [v for _, v in valid_pairs]

        # Step 3: Run all Qdrant searches in parallel
        # Use larger fetch limit when merging multiple result sets
        fetch_limit = params.limit * 3 if len(valid_vectors) > 1 else params.limit

        await ctx.info(f"Searching in collection with {len(valid_vectors)} queries...")
        search_tasks = [
            qdrant.query_points(
                collection_name=params.collection_name,
                query=vec,
                limit=fetch_limit,
                score_threshold=params.score_threshold,
            )
            for vec in valid_vectors
        ]
        raw_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Step 4: Convert each result set to list[dict] format
        all_result_lists = []
        for raw_result in raw_results:
            if isinstance(raw_result, Exception):
                # Skip failed searches
                continue

            matches = []
            for point in raw_result.points:
                match = {
                    "document_id": point.id,
                    "score": point.score,
                }

                # Filter fields if specified
                if params.fields:
                    field_list = [f.strip() for f in params.fields.split(",")]
                    filtered_payload = {k: v for k, v in point.payload.items() if k in field_list}
                    match["metadata"] = filtered_payload
                else:
                    match["metadata"] = point.payload

                matches.append(match)

            all_result_lists.append(matches)

        if not all_result_lists or not all_result_lists[0]:
            return json.dumps({
                "query": params.query_text,
                "collection": params.collection_name,
                "total": 0,
                "message": "No documents found.",
                "search_method": "basic",
            }, ensure_ascii=False)

        # Step 5: Merge if multiple result sets
        if len(all_result_lists) == 1:
            merged = all_result_lists[0]
            search_method = "basic"
        else:
            merged = reciprocal_rank_fusion(all_result_lists)
            search_method = "rrf"
            if params.use_hyde:
                search_method += "+hyde"
            if params.expand_query:
                search_method += "+expand"

        # Step 6: Rerank if requested
        if params.rerank and merged:
            await ctx.info("Reranking results...")
            merged = await rerank_results(params.query_text, merged, params.rerank_top_n)
            search_method += "+rerank"

        # Step 7: Trim to final limit
        final_matches = merged[:params.limit]

        # Step 8: Format and return
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "query": params.query_text,
                "collection": params.collection_name,
                "count": len(final_matches),
                "search_method": search_method,
                "matches": final_matches,
            }, indent=2)
        else:
            # Markdown-style format
            output = {
                "query": params.query_text,
                "collection": params.collection_name,
                "total": len(final_matches),
                "search_method": search_method,
                "results": [],
            }

            if not final_matches:
                output["message"] = "No documents found."
                return json.dumps(output, ensure_ascii=False)

            for i, match in enumerate(final_matches, 1):
                item = {
                    "index": i,
                    "id": match.get("document_id"),
                    "score": round(match.get("score", 0), 4),
                }

                if match.get("metadata"):
                    item["metadata"] = match.get("metadata")

                output["results"].append(item)

            return json.dumps(output, ensure_ascii=False)

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
            # JSON format
            result = {
                "total": len(collection_list),
                "collections": []
            }

            if not collection_list:
                result["message"] = "No collections found."
                return json.dumps(result, ensure_ascii=False)

            for c in collection_list:
                item = {
                    "name": c.get("name"),
                    "points": c.get("points_count", 0),
                    "vectors": c.get("vectors_count", 0),
                    "vector_size": c.get("vector_size", None)
                }

                result["collections"].append(item)

            return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        await ctx.error(f"Failed to list collections: {type(e).__name__}: {e}")
        return json.dumps({
            "error": f"Failed to list collections: {str(e)}"
        })


def main():
    """Entry point for the MCP server."""
    try:
        mcp.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    main()
