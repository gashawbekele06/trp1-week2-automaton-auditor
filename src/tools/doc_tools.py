import pypdf2
from typing import List, Dict
from langchain_core.tools import tool


@tool
def ingest_pdf(pdf_path: str, chunk_size: int = 1000, overlap: int = 200) -> Dict[str, Any]:
    """Ingest PDF, chunk text for RAG-lite, return chunks for querying."""
    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf2.PdfReader(f)
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() or "" + "\n"
        
        # Simple chunking with overlap
        chunks = []
        start = 0
        while start < len(full_text):
            end = min(start + chunk_size, len(full_text))
            chunk = full_text[start:end]
            chunks.append(chunk)
            start = end - overlap
        
        return {"success": True, "chunks": chunks, "total_length": len(full_text)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def query_pdf_chunks(chunks: List[str], query: str) -> List[str]:
    """Simple RAG-lite query: search chunks for keyword matches related to query (e.g., 'What does the report say about Dialectical Synthesis?')."""
    relevant_chunks = []
    lower_query = query.lower()
    for chunk in chunks:
        if lower_query in chunk.lower():
            relevant_chunks.append(chunk)
    return relevant_chunks if relevant_chunks else ["No relevant content found for query."]