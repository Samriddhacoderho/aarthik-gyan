from dotenv import load_dotenv
import os

load_dotenv() 


#Neo4j Configuration
NEO4J_URI=os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

#Google and GROQ API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Qdrant Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  
QDRANT_COLLECTION = "arthikgyaan_chunks"

#Model Configuration
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  
GROQ_MODEL="qwen/qwen3.8-27b"
GEMINI_MODEL="gemini-flash-latest"

# Other Configuration
MAX_EXTRACTION_WORKERS = 3
METRICS_RETRIEVAL_TOP_K = 8
LLM_TIMEOUT_SECONDS = 90
EXTRACTION_CACHE_DIR = ".extraction_cache"

if not NEO4J_URI or not NEO4J_USERNAME or not NEO4J_PASSWORD:
    raise ValueError("Missing Neo4j configuration. Please set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD in your .env file.")

if not GOOGLE_API_KEY:
    raise ValueError("Missing Google API key. Please set GOOGLE_API_KEY in your .env file.")

if not GROQ_API_KEY:
    raise ValueError("Missing GROQ API key. Please set GROQ_API_KEY in your .env file.")

if not QDRANT_URL or not QDRANT_API_KEY or not QDRANT_COLLECTION:
    raise ValueError("Missing Qdrant configuration. Please set QDRANT_URL, QDRANT_API_KEY, and QDRANT_COLLECTION in your .env file.")
