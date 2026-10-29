import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import Optional
import markdown
from weasyprint import HTML

logger = logging.getLogger(__name__)


class PDFGeneratorService:
    """
    Server-Side Rendering (SSR) service that converts Markdown content
    into a professionally formatted A4 PDF document using Markdown + Pygments + WeasyPrint.
    """

    BASE_CSS = """
    @page {
        size: A4;
        margin: 20mm 18mm 22mm 18mm;
        @bottom-left {
            content: "RP_ChatBot • Multi-LLM Technical Document";
            font-family: 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif;
            font-size: 8.5pt;
            color: #64748b;
        }
        @bottom-right {
            content: "Página " counter(page) " de " counter(pages);
            font-family: 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif;
            font-size: 8.5pt;
            color: #64748b;
        }
    }

    body {
        font-family: 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif;
        font-size: 10.5pt;
        line-height: 1.6;
        color: #1e293b;
        margin: 0;
        padding: 0;
    }

    .doc-header {
        border-bottom: 2px solid #4f46e5;
        padding-bottom: 10px;
        margin-bottom: 18px;
    }

    .doc-title {
        font-size: 16pt;
        font-weight: bold;
        color: #0f172a;
        margin: 0 0 4px 0;
    }

    .doc-meta {
        font-size: 8.5pt;
        color: #64748b;
    }

    .doc-badge {
        display: inline-block;
        background-color: #eef2ff;
        color: #4338ca;
        border: 1px solid #c7d2fe;
        border-radius: 4px;
        padding: 1px 6px;
        font-family: 'DejaVu Sans Mono', 'Liberation Mono', monospace;
        font-size: 8pt;
        margin-right: 8px;
    }

    h1, h2, h3, h4 {
        color: #0f172a;
        font-weight: 700;
        margin-top: 16px;
        margin-bottom: 8px;
        page-break-after: avoid;
    }

    h1 {
        font-size: 15pt;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 4px;
    }

    h2 {
        font-size: 13pt;
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 3px;
    }

    h3 {
        font-size: 11.5pt;
    }

    p {
        margin-top: 0;
        margin-bottom: 10px;
        text-align: left;
    }

    ul, ol {
        margin-top: 0;
        margin-bottom: 10px;
        padding-left: 20px;
    }

    li {
        margin-bottom: 4px;
    }

    a {
        color: #4f46e5;
        text-decoration: underline;
        word-break: break-all;
    }

    blockquote {
        margin: 10px 0;
        padding: 8px 14px;
        border-left: 4px solid #6366f1;
        background-color: #f8fafc;
        color: #334155;
        font-style: italic;
        page-break-inside: avoid;
    }

    code {
        font-family: 'DejaVu Sans Mono', 'Liberation Mono', monospace;
        font-size: 9pt;
        background-color: #f1f5f9;
        color: #0f172a;
        padding: 1px 4px;
        border-radius: 3px;
        border: 1px solid #e2e8f0;
    }

    pre, .codehilite pre {
        font-family: 'DejaVu Sans Mono', 'Liberation Mono', monospace;
        font-size: 8.5pt;
        line-height: 1.45;
        background-color: #f8fafc !important;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-left: 3.5px solid #4f46e5;
        border-radius: 6px;
        padding: 10px 12px;
        margin: 10px 0;
        white-space: pre-wrap;
        word-wrap: break-word;
        overflow-wrap: anywhere;
        page-break-inside: avoid;
    }

    pre code, .codehilite code {
        background: transparent;
        border: none;
        padding: 0;
        font-size: inherit;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 9.5pt;
        page-break-inside: avoid;
    }

    th {
        background-color: #f1f5f9;
        color: #0f172a;
        font-weight: 700;
        text-align: left;
        padding: 7px 10px;
        border: 1px solid #cbd5e1;
    }

    td {
        padding: 6px 10px;
        border: 1px solid #cbd5e1;
        vertical-align: top;
    }

    tr:nth-child(even) td {
        background-color: #f8fafc;
    }

    hr {
        border: none;
        border-top: 1px solid #cbd5e1;
        margin: 16px 0;
    }
    """

    @classmethod
    def _render_sync(
        cls,
        markdown_content: str,
        title: str,
        model_name: Optional[str] = None
    ) -> bytes:
        """
        Synchronous CPU-bound pipeline executed inside a worker thread:
        1. Converts Markdown to HTML with GFM tables, fenced code, and syntax highlighting.
        2. Wraps inside a complete HTML5 template with A4 CSS Paged Media styling.
        3. Compiles and returns PDF bytes via WeasyPrint.
        """
        body_html = markdown.markdown(
            markdown_content,
            extensions=[
                "extra",
                "codehilite",
                "sane_lists",
                "toc"
            ],
            extension_configs={
                "codehilite": {
                    "guess_lang": False,
                    "noclasses": True,
                    "pygments_style": "default"
                }
            }
        )

        safe_title = html.escape(title or "Documento Técnico — RP_ChatBot")
        safe_model = html.escape(model_name or "Multi-LLM Workspace")
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        full_html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="utf-8" />
    <title>{safe_title}</title>
    <style>{cls.BASE_CSS}</style>
</head>
<body>
    <div class="doc-header">
        <div class="doc-title">{safe_title}</div>
        <div class="doc-meta">
            <span class="doc-badge">{safe_model}</span>
            <span>Exportado em {timestamp_str}</span>
        </div>
    </div>
    <div class="doc-content">
        {body_html}
    </div>
</body>
</html>"""

        pdf_bytes: bytes = HTML(string=full_html).write_pdf()
        return pdf_bytes

    @classmethod
    async def generate_pdf_bytes(
        cls,
        markdown_content: str,
        title: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> bytes:
        """
        Asynchronously renders Markdown into PDF bytes using asyncio.to_thread
        so the FastAPI Event Loop is never blocked.
        """
        effective_title = (title or "").strip() or "Relatório Técnico — RP_ChatBot"
        return await asyncio.to_thread(
            cls._render_sync,
            markdown_content,
            effective_title,
            model_name
        )

