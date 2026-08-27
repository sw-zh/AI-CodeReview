"""Controlled multi-format document extraction with evidence locators.

Binary formats (PDF, Office, images) are delegated to the online MinerU
precision API; plain and structured text are parsed locally.  No extractor
executes document macros, scripts, embedded objects, archive members or remote
URLs.
"""

from __future__ import annotations

import json
import mimetypes
import zipfile
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
import yaml

from app.core.config import get_settings
from app.domain.ports import DocumentParserPort, ParsedDocumentChunk


class DocumentExtractionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ExtractedDocument:
    media_type: str
    parser_version: str
    chunks: list[ParsedDocumentChunk]
    normalized_text: str
    metadata: dict


class MarkdownTextDocumentParser(DocumentParserPort):
    """Deterministic parser used for plain and normalized extracted text."""

    version = "markdown-text-v2"

    def parse(self, content: str) -> list[ParsedDocumentChunk]:
        normalized = content.replace("\r\n", "\n")
        paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
        values = paragraphs or [normalized.strip()]
        return [
            ParsedDocumentChunk(
                content=value,
                locator={
                    "paragraph": index + 1,
                    "charStart": max(normalized.find(value), 0),
                    "charEnd": max(normalized.find(value), 0) + len(value),
                },
            )
            for index, value in enumerate(values)
            if value
        ]


_EXTENSIONS = {
    ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv",
    ".json": "application/json", ".yaml": "application/yaml", ".yml": "application/yaml",
    ".xml": "application/xml", ".html": "text/html", ".htm": "text/html",
    ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".doc": "application/msword", ".xls": "application/vnd.ms-excel", ".ppt": "application/vnd.ms-powerpoint",
    ".odt": "application/vnd.oasis.opendocument.text", ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".webp": "image/webp", ".tif": "image/tiff", ".tiff": "image/tiff",
}
_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/tiff"}
_LEGACY_OFFICE = {".doc", ".xls", ".ppt", ".odt", ".ods", ".odp"}


def supported_extensions() -> list[str]:
    return sorted(_EXTENSIONS)


def detect_media_type(*, filename: str, claimed_media_type: str | None, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    media_type = _EXTENSIONS.get(extension)
    if media_type is None:
        raise DocumentExtractionError("SOURCE_MEDIA_UNSUPPORTED", "该文件格式暂不支持导入项目知识库")
    if not content:
        raise DocumentExtractionError("SOURCE_EMPTY", "资料内容不能为空")
    if media_type == "application/pdf" and not content.startswith(b"%PDF"):
        raise DocumentExtractionError("SOURCE_MEDIA_MISMATCH", "文件扩展名为 PDF，但文件签名不匹配")
    if media_type == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise DocumentExtractionError("SOURCE_MEDIA_MISMATCH", "PNG 文件签名不匹配")
    if media_type == "image/jpeg" and not content.startswith(b"\xff\xd8"):
        raise DocumentExtractionError("SOURCE_MEDIA_MISMATCH", "JPEG 文件签名不匹配")
    if extension in {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}:
        try:
            with zipfile.ZipFile(__import__("io").BytesIO(content)) as archive:
                names = set(archive.namelist())
                if extension == ".docx" and "word/document.xml" not in names:
                    raise ValueError
                if extension == ".xlsx" and "xl/workbook.xml" not in names:
                    raise ValueError
                if extension == ".pptx" and "ppt/presentation.xml" not in names:
                    raise ValueError
        except (zipfile.BadZipFile, ValueError) as exc:
            raise DocumentExtractionError("SOURCE_MEDIA_MISMATCH", "Office 文件结构不完整或与扩展名不匹配") from exc
    # Browser MIME is advisory only; the extension plus signature is authoritative.
    _ = claimed_media_type or mimetypes.guess_type(filename)[0]
    return media_type


def extract_document(*, content: bytes, filename: str, media_type: str) -> ExtractedDocument:
    """Parse an uploaded source into locatable chunks.

    Plain and structured text are parsed locally (deterministic, low-cost).
    Binary formats (PDF, Office, images) go to the online MinerU precision API,
    which also provides forced OCR for scanned documents.
    """
    extension = Path(filename).suffix.lower()
    if media_type in {"text/plain", "text/markdown", "text/csv"}:
        return _extract_plain(content, media_type)
    if media_type in {"application/json", "application/yaml", "application/xml", "text/html"}:
        return _extract_structured(content, media_type)
    if media_type == "application/pdf" or media_type in _IMAGE_TYPES or extension in _LEGACY_OFFICE or extension in {".docx", ".xlsx", ".pptx"}:
        from app.infrastructure.mineru_client import parse_document_via_mineru

        return parse_document_via_mineru(content=content, filename=filename, settings=get_settings())
    raise DocumentExtractionError("SOURCE_MEDIA_UNSUPPORTED", "该文件格式暂不支持导入项目知识库")


def _extract_plain(content: bytes, media_type: str) -> ExtractedDocument:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentExtractionError("SOURCE_ENCODING_INVALID", "文本资料必须使用 UTF-8 编码") from exc
    chunks = MarkdownTextDocumentParser().parse(text)
    return ExtractedDocument(media_type, "plain-text-v2", chunks, text, {"textLength": len(text)})


def _extract_structured(content: bytes, media_type: str) -> ExtractedDocument:
    try:
        raw = content.decode("utf-8")
        if media_type == "application/json":
            normalized = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        elif media_type == "application/yaml":
            normalized = json.dumps(yaml.safe_load(raw), ensure_ascii=False, indent=2)
        elif media_type == "text/html":
            normalized = BeautifulSoup(raw, "html.parser").get_text("\n", strip=True)
        else:
            normalized = raw
    except Exception as exc:
        raise DocumentExtractionError("SOURCE_PARSER_FAILED", "结构化文本无法安全解析") from exc
    chunks = _line_chunks(normalized, locator_key="line")
    return ExtractedDocument(media_type, "structured-text-v1", chunks, normalized, {"textLength": len(normalized)})


def _line_chunks(text: str, *, locator_key: str) -> list[ParsedDocumentChunk]:
    return [ParsedDocumentChunk(content=line.strip(), locator={locator_key: index}) for index, line in enumerate(text.splitlines(), start=1) if line.strip()]
