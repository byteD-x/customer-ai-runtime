from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from customer_ai_runtime.core.errors import AppError


class ParsedDocument(BaseModel):
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentIngestionService:
    def parse_document(
        self,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> ParsedDocument:
        title = self._title_from_filename(filename)
        normalized_content_type = self._normalize_content_type(content_type)
        extension = Path(filename or "").suffix.lower()
        metadata = {
            "source_filename": filename,
            "content_type": normalized_content_type or content_type,
        }

        if not data:
            raise AppError(
                code="validation_error",
                message="文档内容不能为空。",
                status_code=400,
            )

        if normalized_content_type in {"text/plain", "text/markdown"} or extension in {
            ".txt",
            ".md",
            ".markdown",
        }:
            return ParsedDocument(
                title=title,
                content=self._decode_text(data),
                metadata=metadata,
            )

        if normalized_content_type == "application/pdf" or extension == ".pdf":
            return ParsedDocument(
                title=title,
                content=self._parse_pdf(data),
                metadata=metadata,
            )

        if normalized_content_type in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        } or extension in {".docx", ".doc"}:
            return ParsedDocument(
                title=title,
                content=self._parse_docx(data),
                metadata=metadata,
            )

        raise AppError(
            code="validation_error",
            message=f"不支持的文档类型：{content_type or extension or 'unknown'}。",
            status_code=415,
        )

    def _decode_text(self, data: bytes) -> str:
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError(
                code="validation_error",
                message="文本文件必须使用 UTF-8 编码。",
                status_code=400,
            ) from exc
        if not content.strip():
            raise AppError(
                code="validation_error",
                message="文档内容不能为空。",
                status_code=400,
            )
        return content

    def _parse_pdf(self, data: bytes) -> str:
        try:
            pypdf = importlib.import_module("pypdf")
        except ImportError as exc:
            raise AppError(
                code="provider_error",
                message="解析 PDF 需要安装可选依赖 pypdf。",
                status_code=501,
            ) from exc

        try:
            from io import BytesIO

            reader = pypdf.PdfReader(BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # pragma: no cover - depends on optional parser internals.
            raise AppError(
                code="validation_error",
                message="PDF 文档解析失败。",
                status_code=400,
            ) from exc
        return self._ensure_non_empty("\n".join(pages), "PDF 文档未解析出文本内容。")

    def _parse_docx(self, data: bytes) -> str:
        try:
            docx = importlib.import_module("docx")
        except ImportError as exc:
            raise AppError(
                code="provider_error",
                message="解析 Word 文档需要安装可选依赖 python-docx。",
                status_code=501,
            ) from exc

        try:
            from io import BytesIO

            document = docx.Document(BytesIO(data))
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
        except Exception as exc:  # pragma: no cover - depends on optional parser internals.
            raise AppError(
                code="validation_error",
                message="Word 文档解析失败。",
                status_code=400,
            ) from exc
        return self._ensure_non_empty("\n".join(paragraphs), "Word 文档未解析出文本内容。")

    def _ensure_non_empty(self, content: str, message: str) -> str:
        if not content.strip():
            raise AppError(code="validation_error", message=message, status_code=400)
        return content

    def _title_from_filename(self, filename: str) -> str:
        stem = Path(filename or "").stem.strip()
        return stem or "untitled"

    def _normalize_content_type(self, content_type: str) -> str:
        return (content_type or "").split(";", 1)[0].strip().lower()
