import os
from typing import List, Dict, Tuple
from docling.document_converter import DocumentConverter

def ingest_pdf(pdf_path: str) -> List[Dict[str, str]]:
    """Ingests a PDF using docling and chunks it for RAG-lite querying."""
    if not os.path.exists(pdf_path):
        return [{"error": f"PDF file not found at {pdf_path}"}]

    try:
        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        
        chunks = []
        for item, level in result.document.iterate_items():
             if hasattr(item, 'text'):
                 chunks.append({
                     "type": type(item).__name__,
                     "text": item.text,
                     "level": level
                 })
        return chunks
    except Exception as e:
        return [{"error": f"Failed to ingest PDF: {str(e)}"}]

def query_pdf(chunks: List[Dict[str, str]], keywords: List[str]) -> List[Dict[str, str]]:
    """Explicitly searches chunks for specified keywords to determine theoretical depth."""
    found_evidence = []
    
    if len(chunks) == 1 and "error" in chunks[0]:
         return found_evidence
         
    for chunk in chunks:
        text = chunk.get("text", "").lower()
        if not text:
             continue
             
        for keyword in keywords:
            if keyword.lower() in text:
                found_evidence.append({
                    "keyword": keyword,
                    "context": chunk["text"],
                    "confidence": 0.9 if len(chunk["text"]) > 50 else 0.4 # Longer context usually implies explanation vs buzzword
                })
                
    return found_evidence

def extract_cited_filepaths(chunks: List[Dict[str, str]]) -> List[str]:
    """A naive extraction of file paths formatted implicitly as code locations."""
    # Real implementation could use a better NLP model, but this handles basic forms.
    # We look for patterns like 'src/', '.py', '.ts' etc.
    filepaths = set()
    
    if len(chunks) == 1 and "error" in chunks[0]:
         return list(filepaths)
         
    for chunk in chunks:
        text = chunk.get("text", "")
        words = text.split()
        for word in words:
            # Strip common punctuation that might wrap a filename
            clean_word = word.strip(".,;:\"'()`")
            if "src/" in clean_word or clean_word.endswith(".py"):
                filepaths.add(clean_word)
                
    return list(filepaths)


def extract_images_from_pdf(pdf_path: str, out_dir: str = None) -> List[Dict[str, str]]:
    """Attempt to extract embedded images from a PDF.

    Returns a list of dicts: {"path": <saved_image_path>, "page": <page_index>, "name": <name>}
    If PyMuPDF (fitz) is not available or extraction fails, returns an empty list.
    """
    images = []
    try:
        import fitz  # PyMuPDF
    except Exception:
        return images

    if not os.path.exists(pdf_path):
        return images

    # Create a temporary output directory if not provided
    if out_dir is None:
        import tempfile
        out_dir = tempfile.mkdtemp(prefix="pdf_images_")
    else:
        os.makedirs(out_dir, exist_ok=True)

    try:
        doc = fitz.open(pdf_path)
        for page_index in range(len(doc)):
            page = doc[page_index]
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image.get("image")
                ext = base_image.get("ext", "png")
                name = f"pdf_page{page_index+1}_img{img_index+1}.{ext}"
                out_path = os.path.join(out_dir, name)
                with open(out_path, "wb") as fh:
                    fh.write(image_bytes)
                images.append({"path": out_path, "page": page_index + 1, "name": name})
    except Exception:
        # If extraction fails, return whatever we have (possibly empty)
        return images

    return images
