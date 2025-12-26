#!/usr/bin/env python3
"""
Generate embeddings for documents using different chunking strategies.

This script:
1. Reads all documents from the documents table
2. Splits each document into chunks using different strategies
3. Generates embeddings for each chunk using OpenAI API (in parallel)
4. Stores chunks with embeddings in the chunks table

Strategies format: "model@chunk_size-chunk_overlap"
Example: "text-embedding-3-small@400-200" means:
  - Model: text-embedding-3-small
  - Chunk size: 400 tokens
  - Chunk overlap: 200 tokens
"""
from dotenv import load_dotenv
load_dotenv(".env", override=True)

import asyncio
import json
import os
import sqlite3
from typing import List, Tuple

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI

# Initialize OpenAI client
async_client = AsyncOpenAI()

# Initialize tokenizer
tokenizer = tiktoken.get_encoding("o200k_base")  # gpt-4o uses o200k_base

# Define strategies
STRATEGIES = [
    "text-embedding-3-small@400-200",
    "text-embedding-3-small@800-400",
    "text-embedding-3-large@800-400",
    "text-embedding-3-large@400-200",
]


def length_function(text: str) -> int:
    """Calculate token length of text"""
    return len(tokenizer.encode(text))


def parse_strategy(strategy: str) -> Tuple[str, int, int]:
    """Parse strategy string into model name, chunk_size, and chunk_overlap"""
    model_name, params = strategy.split("@")
    chunk_size, chunk_overlap = map(int, params.split("-"))
    return model_name, chunk_size, chunk_overlap


def create_text_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    """Create a text splitter with specified parameters"""
    return RecursiveCharacterTextSplitter(
        length_function=length_function,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            " ",
            ".",
            ",",
            "\u200b",  # Zero-width space
            "\uff0c",  # Fullwidth comma ،
            "\u3001",  # Ideographic comma 、
            "\uff0e",  # Fullwidth full stop ．
            "\u3002",  # Ideographic full stop 。
            "",
        ],
    )


async def get_embeddings(texts: List[str], model: str) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using OpenAI API.

    Args:
        texts: List of text strings to embed
        model: Name of the embedding model to use

    Returns:
        List of embedding vectors
    """
    response = await async_client.embeddings.create(
        input=texts,
        model=model
    )

    # Return embeddings in the same order as input
    return [data.embedding for data in response.data]


async def process_document_strategy(
    document_id: int,
    filename: str,
    content: str,
    strategy: str,
    conn: sqlite3.Connection
) -> int:
    """
    Process a single document with a specific strategy.

    Args:
        document_id: ID of the document
        filename: Name of the document file
        content: Document content
        strategy: Strategy string (e.g., "text-embedding-3-small@400-200")
        conn: Database connection

    Returns:
        Number of chunks created
    """
    # Parse strategy
    model_name, chunk_size, chunk_overlap = parse_strategy(strategy)

    # Create text splitter
    text_splitter = create_text_splitter(chunk_size, chunk_overlap)

    # Split content into chunks
    chunks = text_splitter.split_text(content)

    if not chunks:
        print(f"    No chunks generated for document {document_id} with strategy {strategy}")
        return 0

    # Prepend filename to each chunk for embedding
    chunks_with_filename = [f"Document filename: {filename}\n\n{chunk}" for chunk in chunks]

    # Generate embeddings for all chunks in parallel (with filename prepended)
    print(f"    Generating {len(chunks)} embeddings for document {document_id} with strategy {strategy}...")
    embeddings = await get_embeddings(chunks_with_filename, model_name)

    # Insert chunks into database
    cursor = conn.cursor()
    for chunk_content, embedding in zip(chunks_with_filename, embeddings):
        # Convert embedding to JSON string for storage
        embedding_json = json.dumps(embedding)

        # Calculate token count for this chunk
        tokens_count = length_function(chunk_content)

        cursor.execute(
            """INSERT INTO chunks (document_id, content, embeddings, strategy, tokens_count)
               VALUES (?, ?, ?, ?, ?)""",
            (document_id, chunk_content, embedding_json, strategy, tokens_count)
        )

    conn.commit()
    print(f"    ✓ Inserted {len(chunks)} chunks for document {document_id} with strategy {strategy}")

    return len(chunks)


async def process_document(
    document_id: int,
    filename: str,
    content: str,
    conn: sqlite3.Connection
) -> int:
    """
    Process a single document with all strategies.

    Args:
        document_id: ID of the document
        filename: Name of the document file
        content: Document content
        conn: Database connection

    Returns:
        Total number of chunks created
    """
    print(f"\n  Processing document {document_id}: {filename}")

    total_chunks = 0

    # Process all strategies in parallel for this document
    tasks = [
        process_document_strategy(document_id, filename, content, strategy, conn)
        for strategy in STRATEGIES
    ]

    results = await asyncio.gather(*tasks)
    total_chunks = sum(results)

    print(f"  ✓ Document {document_id} complete: {total_chunks} total chunks")

    return total_chunks


async def generate_embeddings():
    """Main function to generate embeddings for all documents"""

    # Connect to database
    db_path = "data/documents.db"
    if not os.path.exists(db_path):
        print(f"Error: Database does not exist: {db_path}")
        print("Please run parse_documents.py first")
        return

    conn = sqlite3.connect(db_path)

    # Read all documents
    print("\nReading documents from database...")
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, content FROM documents ORDER BY id")
    documents = cursor.fetchall()

    if not documents:
        print("No documents found in database")
        conn.close()
        return

    print(f"Found {len(documents)} document(s)")
    print(f"Using {len(STRATEGIES)} strategies: {', '.join(STRATEGIES)}")

    # Process each document
    total_chunks = 0
    for doc_id, filename, content in documents:
        chunks_count = await process_document(doc_id, filename, content, conn)
        total_chunks += chunks_count

    conn.close()

    # Print summary
    print("\n" + "="*60)
    print("Summary:")
    print(f"  Documents processed: {len(documents)}")
    print(f"  Strategies used: {len(STRATEGIES)}")
    print(f"  Total chunks created: {total_chunks}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(generate_embeddings())
