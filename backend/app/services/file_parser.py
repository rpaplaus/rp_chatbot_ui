import os
import base64
import asyncio
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class FileParserService:
    """
    Asynchronous file extraction service for user uploaded files.
    All disk I/O and PDF CPU parsing are offloaded to worker threads via asyncio.to_thread.
    """

    SUPPORTED_TEXT_EXTENSIONS = {
        '.txt', '.py', '.md', '.csv', '.json', '.sql', '.js', '.ts', 
        '.jsx', '.tsx', '.html', '.css', '.yaml', '.yml', '.xml', '.sh'
    }

    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    SUPPORTED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a'}

    @classmethod
    async def parse_file(cls, file_path: str) -> Dict[str, Any]:
        """Entrypoint to parse an uploaded file asynchronously."""
        if not os.path.exists(file_path):
            return {
                "type": "error",
                "filename": os.path.basename(file_path),
                "content": f"Arquivo não encontrado: {file_path}",
                "size_bytes": 0
            }
        return await asyncio.to_thread(cls._sync_parse, file_path)

    @classmethod
    def _sync_parse(cls, file_path: str) -> Dict[str, Any]:
        """Synchronous file parsing running inside a worker thread."""
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        size_bytes = os.path.getsize(file_path)

        try:
            # 1. Plain Text and Code Files
            if ext in cls.SUPPORTED_TEXT_EXTENSIONS:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                return {
                    "type": "text",
                    "filename": filename,
                    "content": content,
                    "size_bytes": size_bytes
                }

            # 2. PDF Documents
            elif ext == ".pdf":
                text_content = ""
                try:
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        for page_num, page in enumerate(pdf.pages, start=1):
                            page_text = page.extract_text()
                            if page_text:
                                text_content += f"\n--- Página {page_num} ---\n{page_text}"
                except Exception as pdf_err:
                    text_content = f"[Erro ao extrair conteúdo do PDF: {pdf_err}]"

                return {
                    "type": "text",
                    "filename": filename,
                    "content": text_content.strip(),
                    "size_bytes": size_bytes
                }

            # 3. Images (Base64 Data URI)
            elif ext in cls.SUPPORTED_IMAGE_EXTENSIONS:
                with open(file_path, "rb") as img_file:
                    encoded = base64.b64encode(img_file.read()).decode("utf-8")
                mime_subtype = ext[1:] if ext != ".jpg" else "jpeg"
                return {
                    "type": "image",
                    "filename": filename,
                    "content": f"data:image/{mime_subtype};base64,{encoded}",
                    "size_bytes": size_bytes
                }

            # 4. Audio Files
            elif ext in cls.SUPPORTED_AUDIO_EXTENSIONS:
                return {
                    "type": "audio",
                    "filename": filename,
                    "content": file_path,
                    "size_bytes": size_bytes
                }

            # 5. Fallback Text Reader
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                return {
                    "type": "text",
                    "filename": filename,
                    "content": content,
                    "size_bytes": size_bytes
                }

        except Exception as e:
            logger.error(f"Failed to parse file {filename}: {e}", exc_info=True)
            return {
                "type": "error",
                "filename": filename,
                "content": f"Erro ao processar arquivo {filename}: {str(e)}",
                "size_bytes": size_bytes
            }

