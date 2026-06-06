from __future__ import annotations

import importlib

import pytest

from customer_ai_runtime.application.ingestion import DocumentIngestionService
from customer_ai_runtime.core.errors import AppError


def test_parse_text_document() -> None:
    service = DocumentIngestionService()

    parsed = service.parse_document(
        filename="refund-policy.txt",
        content_type="text/plain; charset=utf-8",
        data="七天无理由退款。".encode(),
    )

    assert parsed.title == "refund-policy"
    assert parsed.content == "七天无理由退款。"
    assert parsed.metadata["source_filename"] == "refund-policy.txt"
    assert parsed.metadata["content_type"] == "text/plain"


def test_parse_markdown_document_by_extension() -> None:
    service = DocumentIngestionService()

    parsed = service.parse_document(
        filename="support.md",
        content_type="application/octet-stream",
        data=b"# Support\n\nResponse SLA is 24 hours.",
    )

    assert parsed.title == "support"
    assert "Response SLA" in parsed.content


def test_parse_empty_document_rejected() -> None:
    service = DocumentIngestionService()

    with pytest.raises(AppError) as error:
        service.parse_document(filename="empty.txt", content_type="text/plain", data=b"")

    assert error.value.code == "validation_error"
    assert error.value.status_code == 400


def test_parse_unknown_document_type_rejected() -> None:
    service = DocumentIngestionService()

    with pytest.raises(AppError) as error:
        service.parse_document(
            filename="archive.bin",
            content_type="application/octet-stream",
            data=b"not a document",
        )

    assert error.value.code == "validation_error"
    assert error.value.status_code == 415


def test_parse_pdf_without_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    service = DocumentIngestionService()
    original_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name == "pypdf":
            raise ImportError("missing pypdf")
        return original_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(AppError) as error:
        service.parse_document(
            filename="guide.pdf",
            content_type="application/pdf",
            data=b"%PDF-1.4",
        )

    assert error.value.code == "provider_error"
    assert "pypdf" in error.value.message


def test_parse_docx_without_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    service = DocumentIngestionService()
    original_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name == "docx":
            raise ImportError("missing python-docx")
        return original_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(AppError) as error:
        service.parse_document(
            filename="guide.docx",
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            data=b"docx bytes",
        )

    assert error.value.code == "provider_error"
    assert "python-docx" in error.value.message
