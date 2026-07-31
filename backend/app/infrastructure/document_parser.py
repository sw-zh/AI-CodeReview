from app.domain.ports import DocumentParserPort, ParsedDocumentChunk


class MarkdownTextDocumentParser(DocumentParserPort):
    """Deterministic v1 parser for UTF-8 Markdown and plain text."""

    version = "markdown-text-v1"

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
        ]
