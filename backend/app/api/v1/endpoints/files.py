import os
import re
import uuid
import aiofiles
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from app.api.deps import get_current_active_user
from app.models.user import User
from app.schemas.upload import FileUploadResponse
from app.services.file_parser import FileParserService

router = APIRouter(prefix="/files", tags=["Files"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

def sanitize_filename(filename: str) -> str:
    """Removes path traversals and dangerous characters from the filename."""
    name = os.path.basename(filename)
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    return safe_name or "arquivo"

@router.post("/upload", response_model=FileUploadResponse, summary="Upload and parse document/attachment (Authenticated)")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    Receives a multipart file from an authenticated user, safely saves it into the uploads volume,
    and performs asynchronous parsing of its contents.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome do arquivo inválido."
        )

    file_id = uuid.uuid4()
    safe_name = sanitize_filename(file.filename)
    stored_filename = f"{file_id}_{safe_name}"
    file_path = os.path.join(UPLOAD_DIR, stored_filename)

    # 1. Save file asynchronously in chunks
    try:
        async with aiofiles.open(file_path, "wb") as out_file:
            while chunk := await file.read(1024 * 64):  # 64KB chunks
                await out_file.write(chunk)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao salvar arquivo no disco: {str(e)}"
        )

    # 2. Extract contents using FileParserService
    parsed_info = await FileParserService.parse_file(file_path)

    return FileUploadResponse(
        file_id=file_id,
        filename=safe_name,
        file_type=parsed_info.get("type", "text"),
        size_bytes=parsed_info.get("size_bytes", 0),
        parsed_content=parsed_info.get("content", ""),
        saved_path=file_path
    )
