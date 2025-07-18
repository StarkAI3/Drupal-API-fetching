import requests
import os
import json
from dotenv import load_dotenv
from embeddings import get_embedding
from pinecone_utils import upsert_vectors, fetch_existing_ids


load_dotenv()



CONTENT_TYPES = [
    'circular',
    'rti_act',
    'mmc_act',
    # Add more content types as needed
]

DATA_DIR = 'data'


def fetch_content(content_type):
    url = f'https://webadmin.pmc.gov.in/api/listing-api/{content_type}?&page_no=1&limit=100&lang=en&vocabulary=department'
    response = requests.get(url, verify=False)
    response.raise_for_status()
    data = response.json()
    print(f"Fetched {content_type} data: {len(data.get('data', {}).get('nodes', []))} items")
    return data.get('data', {}).get('nodes', [])

def save_content_to_file(content, content_type):
    os.makedirs(DATA_DIR, exist_ok=True)
    filename = os.path.join(DATA_DIR, f"{content_type}.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    print(f"Saved {content_type} data to {filename}")
    return filename

def store_in_pinecone(items, content_type):
    vectors = []
    ids = [str(item.get('nid', item.get('id', 'unknown'))) for item in items]
    existing_ids = fetch_existing_ids(ids)
    new_items = [item for item in items if str(item.get('nid', item.get('id', 'unknown'))) not in existing_ids]
    for item in new_items:
        circ_id = str(item.get('nid', item.get('id', 'unknown')))
        circ_text = item.get('title', '') + '\n' + item.get('body', '')
        # Add file URL if present
        file_url = item.get('file')
        if file_url:
            circ_text += f"\nLink: {file_url}"
        embedding = get_embedding(circ_text)
        vectors.append((circ_id, embedding, {'text': circ_text, 'content_type': content_type}))
    if vectors:
        upsert_vectors(vectors)
    print(f"Upserted {len(vectors)} new {content_type} items to Pinecone. Skipped {len(items) - len(new_items)} duplicates.")

def main():
    for content_type in CONTENT_TYPES:
        items = fetch_content(content_type)
        save_content_to_file(items, content_type)
        if items:
            store_in_pinecone(items, content_type)
        else:
            print(f"No items found for content type: {content_type}")
    print("All content saved to the data directory.")

if __name__ == "__main__":
    main() 