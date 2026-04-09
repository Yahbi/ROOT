"""
Content Ingestion Engine — processes files, URLs, and text into ROOT's
memory and knowledge base.

Supports:
- Plain text ingestion with LLM-powered analysis
- URL fetching and knowledge extraction
- File reading: .txt, .md, .pdf, .csv, .json, .html, .py, .js, .ts
- Batch ingestion of mixed content types

PDF reading gracefully degrades: pdfplumber -> PyPDF2 -> raw bytes via LLM.
No hard dependencies on PDF or HTML parsing libraries.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.models.memory import MemoryEntry, MemoryType

logger = logging.getLogger("root.ingestion")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Immutable Result ────────────────────────────────────────────────


@dataclass(frozen=True)
class IngestionResult:
    """Immutable result from a content ingestion operation."""

    source: str
    source_type: str  # "text", "url", "file"
    content_length: int
    facts_extracted: int
    memories_stored: int
    key_points: tuple[str, ...]
    analysis_type: str
    success: bool
    error: str = ""
    timestamp: str = field(default_factory=_now_iso)


# ── File extension → analysis type mapping ──────────────────────────

_CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb",
                    ".java", ".c", ".cpp", ".h", ".swift", ".kt", ".scala",
                    ".sh", ".bash", ".r", ".php"}

_ANALYSIS_TYPE_MAP = {
    ".py": "technical",
    ".js": "technical",
    ".ts": "technical",
    ".jsx": "technical",
    ".tsx": "technical",
    ".go": "technical",
    ".rs": "technical",
    ".java": "technical",
    ".c": "technical",
    ".cpp": "technical",
    ".csv": "general",
    ".json": "technical",
    ".html": "general",
    ".md": "general",
    ".txt": "general",
    ".pdf": "general",
}


# ── Content Ingestion Engine ────────────────────────────────────────


class ContentIngestion:
    """Processes files, URLs, and text into ROOT's memory and knowledge base."""

    def __init__(
        self,
        memory=None,
        experience_memory=None,
        llm=None,
        web_explorer=None,
        document_analyzer=None,
    ) -> None:
        self._memory = memory                    # MemoryEngine
        self._experience_memory = experience_memory  # ExperienceMemory
        self._llm = llm                          # LLM service
        self._web_explorer = web_explorer        # WebExplorer
        self._document_analyzer = document_analyzer  # DocumentAnalyzer
        self._ingestions: int = 0
        self._errors: int = 0
        self._total_memories: int = 0

    # ── Public API ──────────────────────────────────────────────────

    async def ingest_text(
        self,
        text: str,
        source: str = "user_input",
        tags: list[str] | None = None,
    ) -> IngestionResult:
        """Ingest plain text — analyze it and store knowledge in memory.

        1. Analyze text via DocumentAnalyzer for key points, entities, sentiment.
        2. Store each key point as a FACT memory.
        3. Store the full analysis summary as an OBSERVATION.
        4. Return count of items stored.
        """
        tags = tags or []
        if not text.strip():
            return IngestionResult(
                source=source, source_type="text", content_length=0,
                facts_extracted=0, memories_stored=0, key_points=(),
                analysis_type="general", success=False,
                error="Empty text provided",
            )

        try:
            analysis = await self._analyze(text, "general")
            memories_stored = self._store_analysis(
                analysis, source=source, tags=tags,
            )
            self._ingestions += 1
            logger.info(
                "Ingested text from %s: %d key points, %d memories stored",
                source, len(analysis.key_points), memories_stored,
            )
            return IngestionResult(
                source=source, source_type="text",
                content_length=len(text),
                facts_extracted=len(analysis.key_points),
                memories_stored=memories_stored,
                key_points=analysis.key_points,
                analysis_type="general",
                success=True,
            )
        except Exception as exc:
            self._errors += 1
            logger.error("Text ingestion failed for '%s': %s", source[:60], exc)
            return IngestionResult(
                source=source, source_type="text",
                content_length=len(text),
                facts_extracted=0, memories_stored=0, key_points=(),
                analysis_type="general", success=False,
                error=str(exc),
            )

    async def ingest_url(
        self,
        url: str,
        tags: list[str] | None = None,
    ) -> IngestionResult:
        """Ingest a URL — fetch content, analyze, and store knowledge.

        1. Fetch and extract page content via WebExplorer.
        2. Analyze extracted text via DocumentAnalyzer.
        3. Store extracted knowledge in memory with source URL as tag.
        4. Return structured result.
        """
        tags = tags or []
        if not url.strip():
            return IngestionResult(
                source=url, source_type="url", content_length=0,
                facts_extracted=0, memories_stored=0, key_points=(),
                analysis_type="general", success=False,
                error="Empty URL provided",
            )

        try:
            # Fetch page content
            if not self._web_explorer:
                return IngestionResult(
                    source=url, source_type="url", content_length=0,
                    facts_extracted=0, memories_stored=0, key_points=(),
                    analysis_type="general", success=False,
                    error="WebExplorer not available",
                )

            web_content = await self._web_explorer.fetch_and_extract(url)
            content = web_content.text
            if not content or len(content.strip()) < 20:
                return IngestionResult(
                    source=url, source_type="url", content_length=len(content or ""),
                    facts_extracted=0, memories_stored=0, key_points=(),
                    analysis_type="general", success=False,
                    error="No meaningful content extracted from URL",
                )

            # Analyze the content
            analysis = await self._analyze(content, "general")
            url_tags = tags + [url]
            memories_stored = self._store_analysis(
                analysis, source=f"url:{url}", tags=url_tags,
            )

            # Also store the web_content key_facts as separate memories
            for fact in web_content.key_facts:
                self._store_memory(
                    content=fact,
                    memory_type=MemoryType.FACT,
                    source=f"url:{url}",
                    tags=url_tags,
                )
                memories_stored += 1

            self._ingestions += 1
            logger.info(
                "Ingested URL %s: %d key points, %d memories stored",
                url, len(analysis.key_points), memories_stored,
            )
            return IngestionResult(
                source=url, source_type="url",
                content_length=len(content),
                facts_extracted=len(analysis.key_points) + len(web_content.key_facts),
                memories_stored=memories_stored,
                key_points=analysis.key_points,
                analysis_type="general",
                success=True,
            )
        except Exception as exc:
            self._errors += 1
            logger.error("URL ingestion failed for %s: %s", url, exc)
            return IngestionResult(
                source=url, source_type="url", content_length=0,
                facts_extracted=0, memories_stored=0, key_points=(),
                analysis_type="general", success=False,
                error=str(exc),
            )

    async def ingest_file(
        self,
        file_path: str,
        tags: list[str] | None = None,
    ) -> IngestionResult:
        """Ingest a file — read content, analyze, and store knowledge.

        Supported file types:
        - .txt, .md: Read directly as text
        - .pdf: pdfplumber -> PyPDF2 -> LLM raw extraction
        - .csv: Read and summarize structure
        - .json: Parse and summarize structure
        - .html: Strip tags, extract text
        - .py, .js, .ts, etc.: Analyze as code

        Returns structured IngestionResult.
        """
        tags = tags or []
        path = Path(file_path)

        if not path.exists():
            return IngestionResult(
                source=file_path, source_type="file", content_length=0,
                facts_extracted=0, memories_stored=0, key_points=(),
                analysis_type="general", success=False,
                error=f"File not found: {file_path}",
            )

        ext = path.suffix.lower()
        analysis_type = _ANALYSIS_TYPE_MAP.get(ext, "general")

        try:
            content = await self._read_file(path, ext)
            if not content or len(content.strip()) < 10:
                return IngestionResult(
                    source=file_path, source_type="file",
                    content_length=len(content or ""),
                    facts_extracted=0, memories_stored=0, key_points=(),
                    analysis_type=analysis_type, success=False,
                    error="No meaningful content extracted from file",
                )

            # Truncate very large files for analysis
            truncated = content[:50000] if len(content) > 50000 else content

            analysis = await self._analyze(truncated, analysis_type)
            file_tags = tags + [path.name, ext.lstrip(".") or "text"]
            memories_stored = self._store_analysis(
                analysis, source=f"file:{file_path}", tags=file_tags,
            )

            self._ingestions += 1
            logger.info(
                "Ingested file %s (%s): %d key points, %d memories stored",
                path.name, ext, len(analysis.key_points), memories_stored,
            )
            return IngestionResult(
                source=file_path, source_type="file",
                content_length=len(content),
                facts_extracted=len(analysis.key_points),
                memories_stored=memories_stored,
                key_points=analysis.key_points,
                analysis_type=analysis_type,
                success=True,
            )
        except Exception as exc:
            self._errors += 1
            logger.error("File ingestion failed for %s: %s", file_path, exc)
            return IngestionResult(
                source=file_path, source_type="file", content_length=0,
                facts_extracted=0, memories_stored=0, key_points=(),
                analysis_type=analysis_type, success=False,
                error=str(exc),
            )

    async def ingest_batch(
        self, items: list[dict],
    ) -> list[IngestionResult]:
        """Process multiple ingestion items concurrently.

        Each item: {"type": "url"|"text"|"file", "content": "...", "tags": [...]}
        Returns a list of IngestionResult in the same order.
        """
        if not items:
            return []

        async def _process(item: dict) -> IngestionResult:
            item_type = item.get("type", "text")
            content = item.get("content", "")
            item_tags = item.get("tags", [])

            if item_type == "url":
                return await self.ingest_url(content, tags=item_tags)
            elif item_type == "file":
                return await self.ingest_file(content, tags=item_tags)
            else:
                return await self.ingest_text(
                    content, source="batch_input", tags=item_tags,
                )

        results = await asyncio.gather(
            *[_process(item) for item in items],
            return_exceptions=True,
        )

        # Convert exceptions to failed results
        final: list[IngestionResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                item = items[i]
                final.append(IngestionResult(
                    source=item.get("content", "unknown")[:200],
                    source_type=item.get("type", "text"),
                    content_length=0,
                    facts_extracted=0, memories_stored=0, key_points=(),
                    analysis_type="general", success=False,
                    error=str(result),
                ))
            else:
                final.append(result)

        return final

    def stats(self) -> dict:
        """Return ingestion engine statistics."""
        return {
            "total_ingestions": self._ingestions,
            "total_errors": self._errors,
            "total_memories_stored": self._total_memories,
            "has_web_explorer": self._web_explorer is not None,
            "has_document_analyzer": self._document_analyzer is not None,
            "has_memory": self._memory is not None,
            "has_llm": self._llm is not None,
        }

    # ── File Reading ────────────────────────────────────────────────

    async def _read_file(self, path: Path, ext: str) -> str:
        """Read file content based on extension. Runs IO in thread pool."""
        if ext in (".txt", ".md"):
            return await asyncio.to_thread(self._read_text_file, path)
        elif ext == ".pdf":
            return await asyncio.to_thread(self._read_pdf, path)
        elif ext == ".csv":
            return await asyncio.to_thread(self._read_csv, path)
        elif ext == ".json":
            return await asyncio.to_thread(self._read_json, path)
        elif ext == ".html":
            return await asyncio.to_thread(self._read_html, path)
        elif ext in _CODE_EXTENSIONS:
            return await asyncio.to_thread(self._read_text_file, path)
        else:
            # Try as plain text
            return await asyncio.to_thread(self._read_text_file, path)

    @staticmethod
    def _read_text_file(path: Path) -> str:
        """Read a plain text file with encoding fallback."""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1", errors="replace")

    @staticmethod
    def _read_pdf(path: Path) -> str:
        """Read PDF content with graceful library fallback.

        Try order: pdfplumber -> PyPDF2 -> raw bytes (for LLM extraction).
        """
        # 1. Try pdfplumber
        try:
            import pdfplumber
            text_parts: list[str] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            if text_parts:
                logger.debug("PDF read via pdfplumber: %d pages", len(text_parts))
                return "\n\n".join(text_parts)
        except ImportError:
            logger.debug("ImportError suppressed", exc_info=True)
        except Exception as exc:
            logger.warning("pdfplumber failed for %s: %s", path.name, exc)

        # 2. Try PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(path))
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            if text_parts:
                logger.debug("PDF read via PyPDF2: %d pages", len(text_parts))
                return "\n\n".join(text_parts)
        except ImportError:
            logger.debug("ImportError suppressed", exc_info=True)
        except Exception as exc:
            logger.warning("PyPDF2 failed for %s: %s", path.name, exc)

        # 3. Try PyMuPDF (fitz)
        try:
            import fitz
            doc = fitz.open(str(path))
            text_parts = [page.get_text() for page in doc]
            doc.close()
            combined = "\n\n".join(t for t in text_parts if t.strip())
            if combined.strip():
                logger.debug("PDF read via PyMuPDF: %d pages", len(text_parts))
                return combined
        except ImportError:
            logger.debug("ImportError suppressed", exc_info=True)
        except Exception as exc:
            logger.warning("PyMuPDF failed for %s: %s", path.name, exc)

        # 4. Fallback — read raw bytes and decode what we can
        logger.warning(
            "No PDF library available for %s — falling back to raw byte extraction",
            path.name,
        )
        raw = path.read_bytes()
        # Extract readable ASCII/UTF-8 sequences from the PDF binary
        text = raw.decode("latin-1", errors="replace")
        # Strip binary garbage — keep only printable runs
        printable = re.findall(r"[\x20-\x7E\n\r\t]{10,}", text)
        return "\n".join(printable)[:20000] if printable else "[Binary PDF — no text extracted]"

    @staticmethod
    def _read_csv(path: Path) -> str:
        """Read CSV and return a structural summary."""
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1", errors="replace")

        lines = text.strip().split("\n")
        if not lines:
            return ""

        header = lines[0]
        row_count = len(lines) - 1
        # Include header + first 50 rows for analysis
        preview_lines = lines[:51]
        preview = "\n".join(preview_lines)

        return (
            f"CSV File: {path.name}\n"
            f"Columns: {header}\n"
            f"Total rows: {row_count}\n"
            f"--- Data Preview (first {min(50, row_count)} rows) ---\n"
            f"{preview}"
        )

    @staticmethod
    def _read_json(path: Path) -> str:
        """Read JSON and return a structural summary."""
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return f"[JSON parse error: {exc}]"

        # Summarize structure
        def _describe(obj: Any, depth: int = 0) -> str:
            if depth > 3:
                return "..."
            if isinstance(obj, dict):
                keys = list(obj.keys())[:20]
                parts = [f"  {'  ' * depth}{k}: {_describe(obj[k], depth + 1)}" for k in keys]
                extra = f" (+{len(obj) - 20} more keys)" if len(obj) > 20 else ""
                return "{\n" + "\n".join(parts) + extra + "\n" + "  " * depth + "}"
            elif isinstance(obj, list):
                if not obj:
                    return "[]"
                sample = _describe(obj[0], depth + 1)
                return f"[{sample}, ...] ({len(obj)} items)"
            else:
                return repr(obj)[:100]

        structure = _describe(data)
        # Include raw content up to 10K for analysis
        truncated = text[:10000]
        return (
            f"JSON File: {path.name}\n"
            f"Structure:\n{structure}\n\n"
            f"--- Raw Content (first 10K chars) ---\n{truncated}"
        )

    @staticmethod
    def _read_html(path: Path) -> str:
        """Read HTML file and strip tags using regex (no BeautifulSoup needed)."""
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = path.read_text(encoding="latin-1", errors="replace")

        # Strip HTML tags
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ── Analysis Helper ─────────────────────────────────────────────

    async def _analyze(self, text: str, analysis_type: str):
        """Run DocumentAnalyzer.analyze_text, returning AnalysisResult."""
        if self._document_analyzer:
            return await self._document_analyzer.analyze_text(text, analysis_type)

        # Minimal fallback when no analyzer is available
        from backend.core.document_analyzer import AnalysisResult
        words = text.split()
        # Extract rough key points from first few sentences
        sentences = re.split(r"[.!?]\s+", text[:2000])
        key_points = tuple(s.strip() for s in sentences[:5] if len(s.strip()) > 20)
        return AnalysisResult(
            content_type="unknown",
            summary=text[:300],
            key_points=key_points,
            entities={},
            sentiment="neutral",
            recommendations=(),
            word_count=len(words),
        )

    # ── Memory Storage ──────────────────────────────────────────────

    def _store_memory(
        self,
        content: str,
        memory_type: MemoryType,
        source: str,
        tags: list[str],
        confidence: float = 0.85,
    ) -> None:
        """Store a single memory entry, logging failures gracefully."""
        if not self._memory:
            return
        try:
            self._memory.store(MemoryEntry(
                content=content,
                memory_type=memory_type,
                tags=tags,
                source=source,
                confidence=confidence,
            ))
            self._total_memories += 1
        except Exception as exc:
            logger.warning("Failed to store memory: %s", exc)

    def _store_analysis(
        self,
        analysis,
        source: str,
        tags: list[str],
    ) -> int:
        """Store analysis results as memories. Returns count stored."""
        stored = 0

        # Store each key point as a FACT
        for point in analysis.key_points:
            if len(point.strip()) > 10:
                self._store_memory(
                    content=point,
                    memory_type=MemoryType.FACT,
                    source=source,
                    tags=tags + ["ingested"],
                )
                stored += 1

        # Store the full summary as an OBSERVATION
        if analysis.summary and len(analysis.summary.strip()) > 10:
            self._store_memory(
                content=f"[{source}] {analysis.summary}",
                memory_type=MemoryType.OBSERVATION,
                source=source,
                tags=tags + ["analysis", "ingested"],
                confidence=0.9,
            )
            stored += 1

        # Store recommendations as LEARNING entries
        if hasattr(analysis, "recommendations"):
            for rec in analysis.recommendations:
                if len(rec.strip()) > 10:
                    self._store_memory(
                        content=rec,
                        memory_type=MemoryType.LEARNING,
                        source=source,
                        tags=tags + ["recommendation", "ingested"],
                        confidence=0.75,
                    )
                    stored += 1

        return stored
