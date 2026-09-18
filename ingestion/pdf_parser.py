from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
from schemas.entities import parser

def extract_text_from_pdf(file_path: str):
    """Extracts raw text from a PDF. V1 keeps this simple and does not extract tables or images, just the text content."""
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    return docs

def chunk_text(docs):
    """Uses LangChain's text splitter to break the text into smaller chunks for processing."""

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    chunks = text_splitter.split_documents(docs)
    return chunks



