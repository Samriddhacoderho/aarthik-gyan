from dotenv import load_dotenv
import os

load_dotenv() 

NEO4J_URI=os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  
QDRANT_COLLECTION = "arthikgyaan_chunks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  


if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
    raise RuntimeError("Missing Neo4j credentials in .env")
elif not GOOGLE_API_KEY:
    raise RuntimeError("Missing Google API key in .env")
elif not GROQ_API_KEY:
    raise RuntimeError("Missing GROQ API key in .env")
elif not all([QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION]):
    raise RuntimeError("Missing Qdrant configuration in .env")
else:
    pass
