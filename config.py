from dotenv import load_dotenv
import os

load_dotenv() 

NEO4J_URI=os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
    raise RuntimeError("Missing Neo4j credentials in .env")
elif not GOOGLE_API_KEY:
    raise RuntimeError("Missing Google API key in .env")
else:
    pass
