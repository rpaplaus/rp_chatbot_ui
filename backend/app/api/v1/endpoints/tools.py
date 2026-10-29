import re
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_user
from app.models.user import User
from app.services.pdf_generator import PDFGeneratorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["Tools"])


class PDFExportRequest(BaseModel):
    """Payload for exporting a Markdown message to a formatted PDF document."""
    content: str = Field(..., min_length=1, description="Conteúdo em Markdown para conversão em PDF")
    title: Optional[str] = Field(
        default="Relatório Técnico — RP_ChatBot",
        max_length=160,
        description="Título exibido no cabeçalho do documento PDF"
    )
    model_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nome do modelo LLM que gerou a resposta"
    )


@router.post("/pdf", summary="Convert Markdown content into a styled A4 PDF document")
async def export_markdown_to_pdf(
    request: PDFExportRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Renders a Markdown string into a styled PDF binary via WeasyPrint inside a worker thread.
    Requires an authenticated active user.
    """
    try:
        pdf_bytes = await PDFGeneratorService.generate_pdf_bytes(
            markdown_content=request.content,
            title=request.title,
            model_name=request.model_name
        )

        # Build a clean filename
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", (request.title or "rp_chatbot")).strip("_").lower()
        slug = slug[:40] or "rp_chatbot"
        date_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_{date_suffix}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store"
            }
        )
    except Exception as e:
        logger.error(f"Error generating PDF for user '{current_user.username}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao renderizar o documento PDF: {str(e)}"
        )

