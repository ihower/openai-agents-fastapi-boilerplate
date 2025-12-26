from dotenv import load_dotenv
load_dotenv(".env", override=True)
import aiosqlite
import json
from openai import AsyncOpenAI

# Initialize OpenAI client
async_client = AsyncOpenAI()


async def get_embeddings(text, embedding_model: str = "text-embedding-3-small"):
  response = await async_client.embeddings.create(
      input=text,
      model=embedding_model
  )
  return response.data[0].embedding


import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# 參數 list_of_doc_vectors 是所有文件的 embeddings 向量
# 參數 query_vector 是查詢字串的 embedding 向量
# 參數 top_k 是回傳的比數
def get_top_k_indices(list_of_doc_vectors, query_vector, top_k):
  # 轉成 numpy arrays
  list_of_doc_vectors = np.array(list_of_doc_vectors)
  query_vector = np.array(query_vector)

  # 逐筆計算 cosine similarities
  similarities = cosine_similarity(query_vector.reshape(1, -1), list_of_doc_vectors).flatten()

  # 根據 cosine similarity 排序
  sorted_indices = np.argsort(similarities)[::-1]

  # 取出 top K 的索引編號
  top_k_indices = sorted_indices[:top_k]

  return top_k_indices


async def retrieve_documents(query: str, strategy: str = "text-embedding-3-small@800-400", max_k: int = 50) -> list:
    """
    Retrieve top-k most relevant document chunks for a given query.

    Args:
        query: The search query string
        strategy: The embedding strategy to use (must match one used during indexing)
        max_k: Maximum number of chunks to return

    Returns:
        List of dictionaries containing chunk information
    """
    # Get query embeddings
    embedding_model = strategy.split("@")[0]
    query_embeddings = await get_embeddings(query, embedding_model)

    # Connect to database
    db_path = "data/documents.db"
    async with aiosqlite.connect(db_path) as conn:
        # Fetch all chunks with the specified strategy
        async with conn.execute(
            "SELECT id, document_id, content, embeddings FROM chunks WHERE strategy = ?",
            (strategy,)
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            return []

        # Parse embeddings and prepare vectors
        chunk_ids = []
        doc_ids = []
        contents = []
        embeddings_list = []

        for chunk_id, doc_id, content, embeddings_json in rows:
            chunk_ids.append(chunk_id)
            doc_ids.append(doc_id)
            contents.append(content)
            embeddings_list.append(json.loads(embeddings_json))

        #print(f"total chunks: {len(embeddings_list)}")

        # Get top-k most similar chunks
        top_k_indices = get_top_k_indices(embeddings_list, query_embeddings, min(max_k, len(embeddings_list)))

        # Prepare results
        results = []
        for idx in top_k_indices:
            results.append({
                "chunk_id": str(chunk_ids[idx]),
                "document_id": str(doc_ids[idx]),
                "chunk_content": contents[idx],
                "query": query,
                "strategy": strategy
            })

        return results


if __name__ == "__main__":
    import asyncio

    async def test():
        """Test the retrieve_documents function"""
        # Test query
        test_query = "美國餐飲業近況如何?"

        print(f"Testing retrieve_documents with query: '{test_query}'")
        print("="*60)

        # Test with default strategy
        results = await retrieve_documents(
            query=test_query,
            strategy="text-embedding-3-large@400-200",
            max_k=3
        )

        print(f"\nFound {len(results)} results:")
        print("-"*60)

        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Chunk ID: {result['chunk_id']}")
            print(f"  Document ID: {result['document_id']}")
            print(f"  Content preview: {result['chunk_content']}...")

        print("\n" + "="*60)

    asyncio.run(test())

