import os
import io
from pypdf import PdfReader
import docx2txt

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF file bytes."""
    pdf_file = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX file bytes using docx2txt."""
    docx_file = io.BytesIO(file_bytes)
    text = docx2txt.process(docx_file)
    return text

def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract text from plain text file bytes."""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")

def parse_resume(filename: str, file_content: bytes) -> str:
    """Parse resume file based on extension and return text content."""
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == ".pdf":
        return extract_text_from_pdf(file_content)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(file_content)
    elif ext in [".txt", ".md"]:
        return extract_text_from_txt(file_content)
    else:
        raise ValueError(f"Unsupported file format: {ext}")
