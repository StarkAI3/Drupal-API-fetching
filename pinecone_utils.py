import os
from pinecone import Pinecone, ServerlessSpec

PINECONE_API_KEY = os.getenv('PINECONE_API_KEY', 'YOUR_PINECONE_API_KEY')
PINECONE_ENV = os.getenv('PINECONE_ENV', 'YOUR_PINECONE_ENV')
INDEX_NAME = os.getenv('INDEX_NAME', 'circulars-index')
EMBEDDING_DIM = int(os.getenv('EMBEDDING_DIM', 384))

_pc = None
_index = None

def get_index():
    global _pc, _index
    if _pc is None:
        _pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
    if _index is None:
        if INDEX_NAME not in [idx.name for idx in _pc.list_indexes()]:
            _pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIM,
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        _index = _pc.Index(INDEX_NAME)
    return _index

def upsert_vectors(vectors):
    index = get_index()
    index.upsert(vectors)

def fetch_existing_ids(ids):
    index = get_index()
    existing = set()
    for i in range(0, len(ids), 100):
        batch = ids[i:i+100]
        res = index.fetch(ids=batch)
        existing.update(res.vectors.keys())
    return existing

def search_vectors(embedding, top_k=5):
    index = get_index()
    return index.query(vector=embedding, top_k=top_k, include_metadata=True) 