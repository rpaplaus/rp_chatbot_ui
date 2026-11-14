import asyncio
import base64
import logging
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from app.core.config import settings

logger = logging.getLogger(__name__)

MessageContent = Union[str, List[Dict[str, Any]]]
Transcriber = Callable[[str, str], Awaitable[Optional[str]]]
ModalityChecker = Callable[[str], bool]

AUDIO_FORMATS = {".mp3": "mp3", ".wav": "wav", ".ogg": "ogg", ".m4a": "m4a", ".flac": "flac", ".aac": "aac"}


def resolve_upload_path(raw_path: str, upload_dir: Optional[str] = None) -> Optional[str]:
    """
    Returns the real path of an uploaded file only if it lives inside the upload directory.
    The path comes from the client payload, so anything outside UPLOAD_DIR is rejected.
    """
    if not raw_path:
        return None
    base = os.path.realpath(upload_dir or settings.UPLOAD_DIR)
    candidate = os.path.realpath(raw_path)
    try:
        if os.path.commonpath([base, candidate]) != base:
            return None
    except ValueError:
        return None
    return candidate if os.path.isfile(candidate) else None


def _read_audio_b64(path: str) -> Optional[str]:
    if os.path.getsize(path) > settings.MAX_AUDIO_ATTACHMENT_BYTES:
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


async def build_user_content(
    text: str,
    file_contexts: Optional[List[Dict[str, Any]]],
    supports_modality: ModalityChecker,
    transcribe: Optional[Transcriber] = None,
) -> MessageContent:
    """
    Builds the active user message content from its text and attachments.

    - Text/PDF attachments are appended inline as text blocks.
    - Images become `image_url` parts when the model accepts images.
    - Audio becomes an `input_audio` part when the model accepts audio, otherwise it is transcribed.
    Returns a plain string when there is no media, keeping the payload compatible with text-only models.
    """
    if not file_contexts:
        return text

    text_bundle = ""
    media_parts: List[Dict[str, Any]] = []

    for file_data in file_contexts:
        fname = file_data.get("filename", "arquivo")
        ftype = file_data.get("type", "text")
        fcontent = file_data.get("content", "") or ""

        if ftype == "text":
            text_bundle += f"\n\n--- Conteúdo do Arquivo ({fname}) ---\n{fcontent}\n--- Fim do Arquivo ---\n"

        elif ftype == "image":
            if not fcontent.startswith("data:image/"):
                text_bundle += f"\n\n[Imagem anexada '{fname}' inválida ou indisponível.]"
            elif supports_modality("image"):
                media_parts.append({"type": "image_url", "image_url": {"url": fcontent}})
                text_bundle += f"\n\n[Imagem anexada: {fname}]"
            else:
                text_bundle += (
                    f"\n\n[Imagem anexada: {fname} — o modelo selecionado não aceita imagens; "
                    "informe ao usuário que ele deve escolher um modelo com visão para analisá-la.]"
                )

        elif ftype == "audio":
            safe_path = resolve_upload_path(fcontent)
            audio_format = AUDIO_FORMATS.get(os.path.splitext(fname)[1].lower())
            audio_b64 = await asyncio.to_thread(_read_audio_b64, safe_path) if safe_path and audio_format else None

            if not audio_b64:
                logger.warning(f"[Multimodal] Audio attachment '{fname}' rejected (path/format/size).")
                text_bundle += f"\n\n[Áudio anexado '{fname}' indisponível ou em formato não suportado.]"
            elif supports_modality("audio"):
                media_parts.append({"type": "input_audio", "input_audio": {"data": audio_b64, "format": audio_format}})
                text_bundle += f"\n\n[Áudio anexado: {fname}]"
            else:
                transcript = await transcribe(audio_b64, audio_format) if transcribe else None
                if transcript:
                    text_bundle += f"\n\n--- Transcrição do Áudio ({fname}) ---\n{transcript}\n--- Fim da Transcrição ---\n"
                else:
                    text_bundle += f"\n\n[Áudio anexado: {fname} — não foi possível transcrever.]"

        else:
            text_bundle += f"\n\n[Anexo: {fname} - {fcontent}]"

    combined_text = f"{text}{text_bundle}"
    if not media_parts:
        return combined_text
    return [{"type": "text", "text": combined_text}, *media_parts]
