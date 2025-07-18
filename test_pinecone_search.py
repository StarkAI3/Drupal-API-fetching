import os
from dotenv import load_dotenv
from fetch_and_store import get_embedding, search_vectors
from multiprocessing.pool import ApplyResult

load_dotenv()

def test_search(query, top_k=20, keyword=None):
    embedding = get_embedding(query)
    res = search_vectors(embedding, top_k=top_k)
    # Fix: If res is an ApplyResult, call .get() to get the actual result
    if isinstance(res, ApplyResult):
        res = res.get()
    found = False
    print(f"\nTop {top_k} matches for query: '{query}'\n" + '-'*60)
    for i, match in enumerate(res['matches']):
        meta = match['metadata']
        text = meta.get('text', '')
        print(f"[{i+1}] Score: {match['score']:.4f}")
        print(text[:300])  # Print first 300 chars
        if keyword and keyword.lower() in text.lower():
            print("*** FOUND KEYWORD! ***")
            found = True
        print('-'*60)
    if keyword and not found:
        print(f"Keyword '{keyword}' NOT found in top {top_k} results.")

if __name__ == "__main__":
    # You can change the query and keyword below
    test_query = "SAP Sasa-40 Training Workshop"
    keyword = "SAP Sasa-40 Training Workshop"
    test_search(test_query, top_k=20, keyword=keyword) 