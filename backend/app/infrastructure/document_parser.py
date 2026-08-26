"""Controlled multi-format document extraction with evidence locators.

No extractor executes document macros, scripts, embedded objects, archive members or remote URLs.
"""

from __future__ import annotations

import json
import mimetypes
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from docx import Document
from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader
from pptx import Presentation
import pytesseract
import yaml

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


def extract_document(*, content: bytes, filename: str, media_type: str, pdf_max_pages: int, timeout_seconds: int) -> ExtractedDocument:
    extension = Path(filename).suffix.lower()
    if media_type in {"text/plain", "text/markdown", "text/csv"}:
        return _extract_plain(content, media_type)
    if media_type in {"application/json", "application/yaml", "application/xml", "text/html"}:
        return _extract_structured(content, media_type)
    if extension == ".docx":
        return _extract_docx(content, media_type)
    if extension == ".xlsx":
        return _extract_xlsx(content, media_type)
    if extension == ".pptx":
        return _extract_pptx(content, media_type)
    if media_type == "application/pdf":
        return _extract_pdf(content, media_type, pdf_max_pages=pdf_max_pages, timeout_seconds=timeout_seconds)
    if media_type in _IMAGE_TYPES:
        return _extract_image(content, media_type)
    if extension in _LEGACY_OFFICE:
        return _extract_legacy_office(content, extension, media_type, pdf_max_pages=pdf_max_pages, timeout_seconds=timeout_seconds)
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


def _extract_docx(content: bytes, media_type: str) -> ExtractedDocument:
    try:
        document = Document(__import__("io").BytesIO(content))
    except Exception as exc:
        raise DocumentExtractionError("SOURCE_PARSER_FAILED", "Word 文档无法读取") from exc
    chunks: list[ParsedDocumentChunk] = []
    values: list[str] = []
    for number, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()
        if text:
            values.append(text)
            chunks.append(ParsedDocumentChunk(content=text, locator={"paragraph": number}))
    for table_number, table in enumerate(document.tables, start=1):
        for row_number, row in enumerate(table.rows, start=1):
            values = [cell.text.strip() for cell in row.cells]
            text = " | ".join(value for value in values if value)
            if text:
                chunks.append(ParsedDocumentChunk(content=text, locator={"table": table_number, "row": row_number}))
    text = "\n\n".join(item.content for item in chunks)
    return ExtractedDocument(media_type, "docx-v1", chunks, text, {"paragraphs": len(document.paragraphs), "tables": len(document.tables)})


def _extract_xlsx(content: bytes, media_type: str) -> ExtractedDocument:
    try:
        workbook = load_workbook(__import__("io").BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise DocumentExtractionError("SOURCE_PARSER_FAILED", "Excel 工作簿无法读取") from exc
    chunks: list[ParsedDocumentChunk] = []
    for sheet in workbook.worksheets:
        for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            cells = ["" if value is None else str(value) for value in row]
            text = " | ".join(cells).strip(" |")
            if text:
                chunks.append(ParsedDocumentChunk(content=text, locator={"sheet": sheet.title, "range": f"A{row_number}:{_column_name(len(cells))}{row_number}"}))
    text = "\n".join(item.content for item in chunks)
    return ExtractedDocument(media_type, "xlsx-v1", chunks, text, {"sheets": workbook.sheetnames})


def _extract_pptx(content: bytes, media_type: str) -> ExtractedDocument:
    try:
        presentation = Presentation(__import__("io").BytesIO(content))
    except Exception as exc:
        raise DocumentExtractionError("SOURCE_PARSER_FAILED", "PowerPoint 演示稿无法读取") from exc
    chunks: list[ParsedDocumentChunk] = []
    for slide_number, slide in enumerate(presentation.slides, start=1):
        for shape_number, shape in enumerate(slide.shapes, start=1):
            text = getattr(shape, "text", "").strip()
            if text:
                chunks.append(ParsedDocumentChunk(content=text, locator={"slide": slide_number, "shape": shape_number}))
    text = "\n\n".join(item.content for item in chunks)
    return ExtractedDocument(media_type, "pptx-v1", chunks, text, {"slides": len(presentation.slides)})


def _extract_pdf(content: bytes, media_type: str, *, pdf_max_pages: int, timeout_seconds: int) -> ExtractedDocument:
    try:
        reader = PdfReader(__import__("io").BytesIO(content))
        if reader.is_encrypted:
            raise DocumentExtractionError("SOURCE_ENCRYPTED", "受密码保护的 PDF 不能作为知识证据导入")
        if len(reader.pages) > pdf_max_pages:
            raise DocumentExtractionError("SOURCE_PDF_PAGE_LIMIT", f"PDF 页数超过 {pdf_max_pages} 页限制")
    except DocumentExtractionError:
        raise
    except Exception as exc:
        raise DocumentExtractionError("SOURCE_PARSER_FAILED", "PDF 文件无法读取") from exc
    chunks: list[ParsedDocumentChunk] = []
    ocr_pages: list[dict] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if len(text) >= 24:
            chunks.extend(_paragraph_chunks(text, {"page": page_number}))
            continue
        ocr = _ocr_pdf_page(content, page_number, timeout_seconds)
        ocr_pages.append({"page": page_number, "confidence": ocr[1]})
        if ocr[0]:
            chunks.append(ParsedDocumentChunk(content=ocr[0], locator={"page": page_number, "ocr": True, "boxes": ocr[2]}))
    normalized = "\n\n".join(item.content for item in chunks)
    metadata = {"pages": len(reader.pages), "ocrPages": ocr_pages, "ocrConfidence": _average([item["confidence"] for item in ocr_pages]) if ocr_pages else None}
    return ExtractedDocument(media_type, "pdf-v2", chunks, normalized, metadata)


def _extract_image(content: bytes, media_type: str) -> ExtractedDocument:
    try:
        image = Image.open(__import__("io").BytesIO(content))
        image.load()
    except Exception as exc:
        raise DocumentExtractionError("SOURCE_PARSER_FAILED", "图片文件无法读取") from exc
    text, confidence, boxes = _ocr_image(image)
    chunks = [ParsedDocumentChunk(content=text, locator={"image": 1, "ocr": True, "boxes": boxes})] if text else []
    return ExtractedDocument(media_type, "image-ocr-v1", chunks, text, {"ocrConfidence": confidence, "width": image.width, "height": image.height, "ocrPages": [{"page": 1, "confidence": confidence}]})


def _extract_legacy_office(content: bytes, extension: str, media_type: str, *, pdf_max_pages: int, timeout_seconds: int) -> ExtractedDocument:
    with tempfile.TemporaryDirectory(prefix="knowledge-convert-") as directory:
        root = Path(directory)
        source = root / f"source{extension}"
        source.write_bytes(content)
        completed = subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(root), str(source)], capture_output=True, text=True, timeout=timeout_seconds, check=False)
        converted = root / "source.pdf"
        if completed.returncode != 0 or not converted.exists():
            raise DocumentExtractionError("SOURCE_CONVERSION_FAILED", "旧版 Office 文档无法转换为可解析文本")
        result = _extract_pdf(converted.read_bytes(), "application/pdf", pdf_max_pages=pdf_max_pages, timeout_seconds=timeout_seconds)
        return ExtractedDocument(media_type, f"libreoffice-{extension[1:]}-v1", result.chunks, result.normalized_text, {**result.metadata, "convertedFrom": extension})


def _ocr_pdf_page(content: bytes, page_number: int, timeout_seconds: int) -> tuple[str, float, list[dict]]:
    with tempfile.TemporaryDirectory(prefix="knowledge-ocr-") as directory:
        root = Path(directory)
        source = root / "source.pdf"
        prefix = root / "page"
        source.write_bytes(content)
        completed = subprocess.run(["pdftoppm", "-f", str(page_number), "-l", str(page_number), "-png", "-r", "200", str(source), str(prefix)], capture_output=True, text=True, timeout=timeout_seconds, check=False)
        images = list(root.glob("page-*.png"))
        if completed.returncode != 0 or not images:
            raise DocumentExtractionError("SOURCE_OCR_UNAVAILABLE", "扫描 PDF 无法渲染为 OCR 图像")
        with Image.open(images[0]) as image:
            return _ocr_image(image)


def _ocr_image(image: Image.Image) -> tuple[str, float, list[dict]]:
    try:
        data = pytesseract.image_to_data(image, lang="chi_sim+eng", output_type=pytesseract.Output.DICT)
    except Exception as exc:
        raise DocumentExtractionError("SOURCE_OCR_UNAVAILABLE", "OCR 引擎或中文语言包不可用") from exc
    tokens: list[str] = []
    confidences: list[float] = []
    boxes: list[dict] = []
    for index, token in enumerate(data["text"]):
        value = token.strip()
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            confidence = -1.0
        if value and confidence >= 0:
            tokens.append(value)
            confidences.append(confidence)
            boxes.append({"text": value, "x": data["left"][index], "y": data["top"][index], "width": data["width"][index], "height": data["height"][index], "confidence": round(confidence, 2)})
    return " ".join(tokens), _average(confidences), boxes


def _paragraph_chunks(text: str, prefix: dict) -> list[ParsedDocumentChunk]:
    chunks: list[ParsedDocumentChunk] = []
    for paragraph, value in enumerate((part.strip() for part in text.split("\n\n")), start=1):
        if value:
            chunks.append(ParsedDocumentChunk(content=value, locator={**prefix, "paragraph": paragraph}))
    return chunks


def _line_chunks(text: str, *, locator_key: str) -> list[ParsedDocumentChunk]:
    return [ParsedDocumentChunk(content=line.strip(), locator={locator_key: index}) for index, line in enumerate(text.splitlines(), start=1) if line.strip()]


def _column_name(column_count: int) -> str:
    value = max(column_count, 1)
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0
