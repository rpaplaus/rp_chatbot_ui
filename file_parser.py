import os
import base64
import pdfplumber

def parse_file(file_path):
    """
    Parses a file based on its extension and returns text or base64.
    Supported: .txt, .py, .md, .pdf, .jpg, .png
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in ['.txt', '.py', '.md', '.csv', '.json']:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return {"type": "text", "content": f.read()}
            
    elif ext == '.pdf':
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            text = f"[Error reading PDF: {e}]"
        return {"type": "text", "content": text}
        
    elif ext in ['.jpg', '.jpeg', '.png']:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        mime_type = "image/jpeg" if ext in ['.jpg', '.jpeg'] else "image/png"
        return {"type": "image", "content": f"data:{mime_type};base64,{encoded_string}"}
        
    elif ext in ['.mp3', '.wav']:
         return {"type": "audio", "content": file_path}
         
    else:
        # Fallback for code files and others
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return {"type": "text", "content": f.read()}
        except Exception:
            return {"type": "unknown", "content": f"Unsupported or unreadable file type: {ext}"}
