import uuid
from pydantic import BaseModel, Field

class FileUploadResponse(BaseModel):
    """Response returned upon successful file upload and extraction."""
    file_id: uuid.UUID
    filename: str = Field(..., example="relatorio.pdf")
    file_type: str = Field(..., example="text")
    size_bytes: int = Field(..., example=1024)
    parsed_content: str = Field(..., example="Conteúdo extraído...")
    saved_path: str = Field(..., example="/app/uploads/1234_relatorio.pdf")

