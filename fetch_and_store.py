import requests
import os
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
import json
from dotenv import load_dotenv
load_dotenv()
import certifi
print(certifi.where())

# Set your Pinecone API key and environment here or use environment variables
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY', 'YOUR_PINECONE_API_KEY')

# Pinecone index name
INDEX_NAME = 'circulars-index'
# Embedding model and dimension
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
EMBEDDING_DIM = 384

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

# Fetch data from Drupal API
def fetch_circulars():
    url = 'https://webadmin.pmc.gov.in/api/listing-api/circular?&page_no=1&limit=20&lang=en&vocabulary=department'
    response = requests.get(url, verify=False)
    response.raise_for_status()
    data = response.json()
    print("Fetched data:", data)
    return data.get('data', {}).get('nodes', [])

# Get SentenceTransformer embeddings
def get_embedding(model, text):
    return model.encode(text).tolist()

# Store data in Pinecone
def store_in_pinecone(circulars):
    vectors = []
    for circ in circulars:
        if not isinstance(circ, dict):
            continue  # Skip if not a dict
        circ_id = str(circ.get('nid', circ.get('id', 'unknown')))
        circ_text = circ.get('title', '') + '\n' + circ.get('body', '')
        embedding = get_embedding(model, circ_text)
        vectors.append((circ_id, embedding, {'text': circ_text}))
    if vectors:
        index.upsert(vectors)
    print(f"Upserted {len(vectors)} circulars to Pinecone.")

def save_circulars_to_file(circulars, filename='circulars_raw.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(circulars, f, ensure_ascii=False, indent=2)

def main():
    circulars = fetch_circulars()
    if not circulars:
        print("No circulars found.")
        return
    save_circulars_to_file(circulars)
    store_in_pinecone(circulars)

if __name__ == "__main__":
    main() 