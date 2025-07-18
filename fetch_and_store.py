import requests
import os
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
import json
from dotenv import load_dotenv
from datetime import datetime
import certifi

load_dotenv()
print(certifi.where())

# Set your Pinecone API key and environment here or use environment variables
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY', 'YOUR_PINECONE_API_KEY')

# Pinecone index name
INDEX_NAME = 'pmcbot'
# Embedding model and dimension
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
EMBEDDING_DIM = 384

# List of content types to fetch (add more as needed)
CONTENT_TYPES = [
    'circular',
    'rti_act',
    'mmc_act',
]

DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)

pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY', 'YOUR_PINECONE_API_KEY'))

# Create index if it doesn't exist
if INDEX_NAME not in [index.name for index in pc.list_indexes()]:
    pc.create_index(
        name=INDEX_NAME,
        dimension=EMBEDDING_DIM,
        spec=ServerlessSpec(
            cloud="aws",  # or "gcp"
            region="us-east-1"  # or your preferred region
        )
    )

# Connect to the index
index = pc.Index(INDEX_NAME)
model = SentenceTransformer(EMBEDDING_MODEL_NAME)

def fetch_content(content_type):
    url = f'https://webadmin.pmc.gov.in/api/listing-api/{content_type}?&page_no=1&limit=1000&lang=en&vocabulary=department'
    response = requests.get(url, verify=False)
    response.raise_for_status()
    data = response.json()
    print(f"Fetched {content_type} data: count=", len(data.get('data', {}).get('nodes', [])))
    return data.get('data', {}).get('nodes', [])

def get_embedding(text):
    """Get embedding for a single text input (for chatbot_server compatibility)."""
    return model.encode(text).tolist()

def search_vectors(embedding, top_k=5):
    """Search Pinecone index for similar vectors."""
    return index.query(vector=embedding, top_k=top_k, include_metadata=True)

def load_existing_ids(filepath):
    if not os.path.exists(filepath):
        return set()
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return set(str(item.get('nid', item.get('id', 'unknown'))) for item in data)
        except Exception:
            return set()

def save_content_to_file(content, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

def store_in_pinecone(content, content_type):
    vectors = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get('nid', item.get('id', 'unknown')))
        # Try to get a link if available
        link = item.get('url', '') or item.get('link', '')
        circ_text = item.get('title', '') + '\n' + item.get('body', '')
        if link:
            circ_text += f'\n{link}'
        embedding = get_embedding(circ_text)
        vectors.append((f"{content_type}_{item_id}", embedding, {'text': circ_text, 'content_type': content_type}))
    if vectors:
        index.upsert(vectors)
    print(f"Upserted {len(vectors)} {content_type} items to Pinecone.")

def main():
    for content_type in CONTENT_TYPES:
        print(f"Processing content type: {content_type}")
        filepath = os.path.join(DATA_DIR, f"{content_type}.json")
        existing_ids = load_existing_ids(filepath)
        new_content = fetch_content(content_type)
        # Filter out already existing items
        new_items = [item for item in new_content if str(item.get('nid', item.get('id', 'unknown'))) not in existing_ids]
        if not new_items:
            print(f"No new {content_type} items found.")
            continue
        # Save all (merged) items to file
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    old_data = json.load(f)
                except Exception:
                    old_data = []
            merged = old_data + new_items
        else:
            merged = new_items
        save_content_to_file(merged, filepath)
        store_in_pinecone(new_items, content_type)

if __name__ == "__main__":
    main() 