import pypdf2
from PIL import Image
import io
from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool


@tool
def extract_images_from_pdf(pdf_path: str) -> List[str]:
    """Extract images from PDF, save to temporary PNG files, return paths."""
    try:
        reader = pypdf2.PdfReader(pdf_path)
        image_paths = []
        for page_num, page in enumerate(reader.pages):
            if '/XObject' in page['/Resources']:
                xobjects = page['/Resources']['/XObject'].get_object()
                for obj in xobjects:
                    if xobjects[obj]['/Subtype'] == '/Image':
                        img = xobjects[obj]
                        img_data = img.get_data()
                        img = Image.open(io.BytesIO(img_data))
                        img_path = f"temp_img_page{page_num}_{obj.strip('/')}.png"
                        img.save(img_path)
                        image_paths.append(img_path)
        return image_paths if image_paths else ["No images found in PDF."]
    except Exception as e:
        return [str(e)]


@tool
def analyze_extracted_image(image_path: str, question: str = "Is this a StateGraph diagram or a generic box diagram?") -> Dict[str, str]:
    """Analyze extracted image with multimodal LLM (optional run)."""
    # NOTE: Running is optional per scope — comment out LLM call if not testing
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)  # Vision-capable model
        prompt = f"Analyze this diagram: {question}"
        # To run: pass image to LLM (requires langchain image message)
        # from langchain_core.messages import HumanMessage
        # msg = HumanMessage(content=[{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"file://{image_path}"}}])
        # response = llm.invoke([msg])
        # return {"analysis": response.content}
        
        # Placeholder for optional run
        return {"analysis": "Vision analysis not executed (optional scope). Image path: " + image_path}
    except Exception as e:
        return {"error": str(e)}