from dotenv import load_dotenv
load_dotenv()
import os
from pinecone import Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"), environment=os.getenv("PINECONE_ENV"))
print(pc.list_indexes())


print(os.getenv("PINECONE_API_KEY"))
print(os.getenv("PINECONE_ENV"))