import os
from fetch_and_store import get_embedding, search_vectors

# Sample query to debug
QUERY = "Regarding the Report of the Clerk"
TOP_K = 5

embedding = get_embedding(QUERY)
res = search_vectors(embedding, top_k=TOP_K)

print(f"\nDEBUG: Pinecone search results for query: '{QUERY}' (top {TOP_K})\n")
for i, match in enumerate(res['matches']):
    print(f"Match {i+1}:")
    print(f"  ID: {match.get('id')}")
    print(f"  Score: {match.get('score')}")
    print(f"  Metadata: {match.get('metadata')}")
    print("-"*60) 