"""
Document Analyzer — ROOT's autonomous document analysis, report generation,
and export engine.

Capabilities:
1. Analyze text and files (general, financial, technical, scientific, legal)
2. Generate structured reports from data (markdown, HTML)
3. Export content to professional HTML with CSS styling
4. Summarize text with LLM-powered compression
5. Extract named entities (companies, people, dates, numbers, etc.)
6. Compare two documents for similarities and differences
7. Study topics in depth — break into subtopics, analyze each, synthesize

All analysis flows through the LLM for deep understanding. Results are
stored in memory so ROOT accumulates domain knowledge over time.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("root.document_analyzer")


# ── Frozen Dataclasses ───────────────────────────────────────────────


@dataclass(frozen=True)
class AnalysisResult:
    """Immutable result from document analysis."""

    content_type: str
    summary: str
    key_points: tuple[str, ...]
    entities: dict  # {type: [values]}
    sentiment: str  # "positive", "negative", "neutral", "mixed"
    recommendations: tuple[str, ...]
    word_count: int


@dataclass(frozen=True)
class StudyResult:
    """Immutable result from a comprehensive topic study."""

    topic: str
    subtopics: tuple[str, ...]
    findings: tuple[str, ...]
    synthesis: str
    knowledge_stored: int
    sources_consulted: int


# ── File Extension Map ───────────────────────────────────────────────

_SUPPORTED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".py", ".html"}

# ── Analysis Prompts ─────────────────────────────────────────────────

_ANALYSIS_SYSTEM = """You are ROOT's Document Analyzer — an expert at extracting structured insights from text.

Analyze the given text and return a JSON object with exactly these fields:
{
    "content_type": "<detected type: article, report, code, data, legal, financial, scientific, conversation, other>",
    "summary": "<concise 2-4 sentence summary>",
    "key_points": ["<point 1>", "<point 2>", ...],
    "entities": {
        "companies": ["..."],
        "people": ["..."],
        "dates": ["..."],
        "numbers": ["..."],
        "currencies": ["..."],
        "percentages": ["..."],
        "tickers": ["..."]
    },
    "sentiment": "<positive|negative|neutral|mixed>",
    "recommendations": ["<actionable recommendation 1>", ...]
}

Rules:
- Be precise and factual — do not hallucinate entities.
- Key points should capture the most important ideas.
- Recommendations should be actionable and relevant.
- If a field has no values, use an empty list or appropriate default.
- Return ONLY valid JSON, no markdown fences, no commentary."""

_ANALYSIS_TYPE_INSTRUCTIONS = {
    "general": "Provide a comprehensive general analysis covering all aspects of the text.",
    "financial": (
        "Focus on financial metrics, market signals, risk factors, revenue figures, "
        "growth rates, valuations, and investment implications. Extract all monetary "
        "values, percentages, and financial entities."
    ),
    "technical": (
        "Focus on technical architecture, algorithms, technologies mentioned, "
        "implementation details, performance characteristics, and technical debt. "
        "Identify frameworks, languages, and design patterns."
    ),
    "scientific": (
        "Focus on hypotheses, methodology, results, statistical significance, "
        "limitations, citations, and future research directions. Identify key "
        "findings and their confidence levels."
    ),
    "legal": (
        "Focus on legal obligations, rights, clauses, liabilities, compliance "
        "requirements, defined terms, and potential risks. Identify parties, "
        "dates, and governing law."
    ),
}

_SUMMARIZE_SYSTEM = """You are ROOT's summarization module. Produce a clear, concise summary
that captures the essential information. Do not add opinions or information not present
in the original text. Return ONLY the summary text, nothing else."""

_ENTITY_SYSTEM = """You are ROOT's entity extraction module. Extract named entities from the text.

Return a JSON object with exactly these keys:
{
    "companies": ["..."],
    "people": ["..."],
    "dates": ["..."],
    "numbers": ["..."],
    "currencies": ["..."],
    "percentages": ["..."],
    "tickers": ["..."]
}

Rules:
- Only extract entities actually present in the text.
- Tickers are stock/crypto symbols (e.g., AAPL, BTC).
- Currencies include amounts with currency symbols or names (e.g., "$1.5M", "500 EUR").
- Return ONLY valid JSON, no markdown fences."""

_COMPARE_SYSTEM = """You are ROOT's document comparison module. Compare two documents and identify
their similarities, differences, and unique points.

Return a JSON object:
{
    "similarities": ["<shared theme or point 1>", ...],
    "differences": ["<difference 1>", ...],
    "unique_to_a": ["<point only in Document A>", ...],
    "unique_to_b": ["<point only in Document B>", ...],
    "overall_assessment": "<1-2 sentence summary of how the documents relate>"
}

Return ONLY valid JSON, no markdown fences."""

_STUDY_SYSTEM = """You are ROOT's deep research module. Given a topic, break it down into
subtopics for comprehensive study.

Return a JSON object:
{
    "subtopics": ["<subtopic 1>", "<subtopic 2>", ...],
    "key_questions": ["<question to answer for each subtopic>", ...]
}

For "standard" depth: 4-6 subtopics.
For "deep" depth: 8-12 subtopics with more granular breakdown.
For "surface" depth: 2-3 high-level subtopics.

Return ONLY valid JSON, no markdown fences."""

_STUDY_SYNTHESIZE_SYSTEM = """You are ROOT's research synthesis module. Given findings from
studying multiple subtopics, produce a cohesive synthesis.

Return a JSON object:
{
    "synthesis": "<comprehensive synthesis paragraph connecting all findings>",
    "key_findings": ["<finding 1>", "<finding 2>", ...],
    "knowledge_gaps": ["<what still needs investigation>", ...]
}

Return ONLY valid JSON, no markdown fences."""

_REPORT_SYSTEM = """You are ROOT's report generation module. Given a topic and data, produce
a structured report in {format} format.

The report MUST include these sections in order:
1. Executive Summary
2. Key Findings
3. Data Analysis
4. Recommendations
5. Appendix

Rules:
- Use the provided data to support every claim.
- Be precise, professional, and data-driven.
- Include specific numbers and metrics where available.
- The report should be self-contained and actionable."""

# ── HTML Template ────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --primary: #1a1a2e;
            --secondary: #16213e;
            --accent: #0f3460;
            --highlight: #e94560;
            --text: #eee;
            --text-muted: #aab;
            --bg: #0f0f1a;
            --card-bg: #1a1a2e;
            --border: #2a2a4a;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            padding: 0;
        }}
        .header {{
            background: linear-gradient(135deg, var(--primary), var(--accent));
            padding: 3rem 2rem;
            border-bottom: 3px solid var(--highlight);
        }}
        .header h1 {{
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        .header .meta {{
            color: var(--text-muted);
            font-size: 0.9rem;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
        }}
        .toc {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem 2rem;
            margin-bottom: 2rem;
        }}
        .toc h2 {{
            font-size: 1.1rem;
            color: var(--highlight);
            margin-bottom: 0.75rem;
        }}
        .toc ul {{
            list-style: none;
            padding: 0;
        }}
        .toc li {{
            padding: 0.3rem 0;
        }}
        .toc a {{
            color: var(--text-muted);
            text-decoration: none;
            transition: color 0.2s;
        }}
        .toc a:hover {{
            color: var(--highlight);
        }}
        .section {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 1.5rem;
        }}
        .section h2 {{
            font-size: 1.4rem;
            color: var(--highlight);
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }}
        .section h3 {{
            font-size: 1.1rem;
            color: var(--text);
            margin: 1rem 0 0.5rem;
        }}
        .section p {{
            margin-bottom: 0.75rem;
            color: var(--text-muted);
        }}
        .section ul, .section ol {{
            margin: 0.5rem 0 1rem 1.5rem;
            color: var(--text-muted);
        }}
        .section li {{
            margin-bottom: 0.3rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }}
        th, td {{
            padding: 0.6rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background: var(--secondary);
            color: var(--highlight);
            font-weight: 600;
        }}
        tr:hover {{
            background: rgba(233, 69, 96, 0.05);
        }}
        code {{
            background: var(--secondary);
            padding: 0.15rem 0.4rem;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        pre {{
            background: var(--secondary);
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
            margin: 0.75rem 0;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }}
        .footer strong {{
            color: var(--highlight);
        }}
        @media print {{
            body {{ background: #fff; color: #333; }}
            .header {{ background: #333; }}
            .section {{ border-color: #ddd; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>{title}</h1>
            <div class="meta">Generated on {date} &middot; ROOT AI Document Analyzer</div>
        </div>
    </div>
    <div class="container">
        {toc}
        {body}
    </div>
    <div class="footer">
        <strong>Generated by ROOT AI</strong> &middot; Autonomous Document Analysis Engine
    </div>
</body>
</html>"""


# ── Helpers ──────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json_response(text: str) -> dict:
    """Best-effort parse JSON from LLM response, stripping markdown fences."""
    cleaned = text.strip()
    # Strip ```json ... ``` fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Drop first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                logger.debug("Failed to extract JSON object from LLM response text", exc_info=True)
        logger.warning("Failed to parse JSON from LLM response, returning empty dict")
        return {}


def _build_toc(sections: list[tuple[str, str]]) -> str:
    """Build an HTML table of contents from (id, title) pairs."""
    if not sections:
        return ""
    items = "\n".join(
        f'            <li><a href="#{sid}">{title}</a></li>'
        for sid, title in sections
    )
    return f"""<div class="toc">
            <h2>Table of Contents</h2>
            <ul>
{items}
            </ul>
        </div>"""


def _markdown_to_html_sections(content: str) -> tuple[str, list[tuple[str, str]]]:
    """Convert markdown-ish content to HTML sections.

    Returns (html_body, toc_entries) where toc_entries are (id, title) pairs.
    """
    sections: list[tuple[str, str]] = []
    html_parts: list[str] = []
    current_section_id: Optional[str] = None
    current_lines: list[str] = []

    def _flush() -> None:
        if current_lines:
            body = "\n".join(current_lines)
            # Convert markdown lists
            body = re.sub(r"^- (.+)$", r"<li>\1</li>", body, flags=re.MULTILINE)
            if "<li>" in body:
                body = re.sub(
                    r"((?:<li>.+</li>\n?)+)",
                    r"<ul>\1</ul>",
                    body,
                )
            # Convert bold
            body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body)
            # Wrap plain text in paragraphs
            paragraphs: list[str] = []
            for block in body.split("\n\n"):
                block = block.strip()
                if not block:
                    continue
                if block.startswith("<"):
                    paragraphs.append(block)
                else:
                    paragraphs.append(f"<p>{block}</p>")
            inner = "\n            ".join(paragraphs)
            if current_section_id:
                html_parts.append(
                    f'        <div class="section" id="{current_section_id}">\n'
                    f"            {inner}\n"
                    f"        </div>"
                )
            else:
                html_parts.append(f'        <div class="section">\n            {inner}\n        </div>')

    for line in content.split("\n"):
        stripped = line.strip()
        # Detect markdown headings
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            _flush()
            current_lines = []
            level = len(heading_match.group(1))
            title = heading_match.group(2)
            sid = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            sections.append((sid, title))
            current_section_id = sid
            tag = f"h{level + 1}" if level > 1 else "h2"
            current_lines.append(f"<{tag}>{title}</{tag}>")
        else:
            current_lines.append(stripped)

    _flush()

    return "\n".join(html_parts), sections


# ── Main Class ───────────────────────────────────────────────────────


class DocumentAnalyzer:
    """Autonomous document analysis, report generation, and export engine."""

    def __init__(self, llm=None, memory=None) -> None:
        self._llm = llm
        self._memory = memory
        self._analyses_count: int = 0
        self._reports_generated: int = 0
        self._exports_count: int = 0
        self._entities_extracted: int = 0
        self._comparisons_count: int = 0
        self._studies_count: int = 0
        self._summaries_count: int = 0

    # ── Internal LLM Calls ───────────────────────────────────────

    async def _llm_complete(
        self,
        system: str,
        user_content: str,
        *,
        model_tier: str = "default",
        max_tokens: int = 2000,
    ) -> str:
        """Call the LLM and return the text response."""
        if not self._llm:
            raise RuntimeError("DocumentAnalyzer requires an LLM service")
        response = await self._llm.complete(
            system=system,
            messages=[{"role": "user", "content": user_content}],
            model_tier=model_tier,
            max_tokens=max_tokens,
        )
        return response.strip()

    async def _store_memory(self, content: str, tags: list[str]) -> None:
        """Store a finding in ROOT's memory if available."""
        if not self._memory:
            return
        try:
            self._memory.add(
                content=content,
                memory_type="knowledge",
                source="document_analyzer",
                tags=tags,
            )
        except Exception as exc:
            logger.warning("Failed to store memory: %s", exc)

    # ── Core Analysis ────────────────────────────────────────────

    async def analyze_text(
        self, text: str, analysis_type: str = "general"
    ) -> AnalysisResult:
        """Analyze text using the LLM.

        Args:
            text: The text to analyze.
            analysis_type: One of "general", "financial", "technical",
                           "scientific", "legal".

        Returns:
            AnalysisResult with structured analysis data.
        """
        if analysis_type not in _ANALYSIS_TYPE_INSTRUCTIONS:
            logger.warning(
                "Unknown analysis_type %r, falling back to 'general'", analysis_type
            )
            analysis_type = "general"

        type_instruction = _ANALYSIS_TYPE_INSTRUCTIONS[analysis_type]
        word_count = len(text.split())

        prompt = (
            f"Analysis type: {analysis_type}\n"
            f"Instructions: {type_instruction}\n\n"
            f"--- TEXT TO ANALYZE (word count: {word_count}) ---\n\n"
            f"{text}"
        )

        try:
            raw = await self._llm_complete(
                system=_ANALYSIS_SYSTEM,
                user_content=prompt,
                model_tier="default",
                max_tokens=2500,
            )
            data = _parse_json_response(raw)
        except Exception as exc:
            logger.error("LLM analysis failed: %s", exc)
            # Return a minimal result on failure
            return AnalysisResult(
                content_type="unknown",
                summary=f"Analysis failed: {exc}",
                key_points=(),
                entities={},
                sentiment="neutral",
                recommendations=(),
                word_count=word_count,
            )

        entities = data.get("entities", {})
        # Ensure all entity keys exist even if LLM omitted them
        for key in ("companies", "people", "dates", "numbers", "currencies", "percentages", "tickers"):
            if key not in entities:
                entities[key] = []

        result = AnalysisResult(
            content_type=data.get("content_type", "unknown"),
            summary=data.get("summary", ""),
            key_points=tuple(data.get("key_points", [])),
            entities=entities,
            sentiment=data.get("sentiment", "neutral"),
            recommendations=tuple(data.get("recommendations", [])),
            word_count=word_count,
        )

        self._analyses_count += 1
        logger.info(
            "Analyzed %d-word %s text — type=%s, sentiment=%s, %d key points",
            word_count,
            analysis_type,
            result.content_type,
            result.sentiment,
            len(result.key_points),
        )

        # Store summary in memory
        await self._store_memory(
            f"Document analysis ({analysis_type}): {result.summary}",
            ["document_analysis", analysis_type, result.content_type],
        )

        return result

    async def analyze_file(self, file_path: str) -> AnalysisResult:
        """Read a file and analyze its contents.

        Supports: .txt, .md, .csv, .json, .py, .html

        Args:
            file_path: Path to the file to analyze.

        Returns:
            AnalysisResult from analyzing the file content.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type {ext!r}. Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
            )

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")

        # Infer analysis type from extension
        analysis_type = "general"
        if ext == ".py":
            analysis_type = "technical"
        elif ext == ".json":
            analysis_type = "technical"
        elif ext == ".csv":
            analysis_type = "financial"

        logger.info("Analyzing file %s (%s, %d chars)", path.name, ext, len(content))
        return await self.analyze_text(content, analysis_type=analysis_type)

    # ── Report Generation ────────────────────────────────────────

    async def generate_report(
        self, topic: str, data: dict, format: str = "markdown"
    ) -> str:
        """Generate a structured report from data.

        Args:
            topic: The report topic/title.
            data: Dictionary of data to include in the report.
            format: Output format — "markdown" or "html".

        Returns:
            The generated report as a string.
        """
        if format not in ("markdown", "html"):
            logger.warning("Unknown format %r, defaulting to 'markdown'", format)
            format = "markdown"

        system = _REPORT_SYSTEM.format(format=format)
        prompt = (
            f"Topic: {topic}\n\n"
            f"Data:\n{json.dumps(data, indent=2, default=str)}\n\n"
            f"Generate a comprehensive {format} report with Executive Summary, "
            f"Key Findings, Data Analysis, Recommendations, and Appendix sections."
        )

        try:
            report = await self._llm_complete(
                system=system,
                user_content=prompt,
                model_tier="default",
                max_tokens=4000,
            )
        except Exception as exc:
            logger.error("Report generation failed: %s", exc)
            raise RuntimeError(f"Failed to generate report: {exc}") from exc

        self._reports_generated += 1
        logger.info(
            "Generated %s report on %r (%d chars)", format, topic, len(report)
        )

        await self._store_memory(
            f"Generated report on '{topic}' ({format}, {len(report)} chars)",
            ["report_generation", topic.lower().replace(" ", "_")],
        )

        return report

    # ── HTML Export ───────────────────────────────────────────────

    async def export_html(
        self, content: str, title: str = "ROOT Report"
    ) -> str:
        """Wrap content in a professional HTML template.

        Args:
            content: Markdown or plain text content.
            title: Report title for the header.

        Returns:
            Complete HTML string ready to be saved or served.
        """
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
        body_html, toc_entries = _markdown_to_html_sections(content)
        toc_html = _build_toc(toc_entries)

        html = _HTML_TEMPLATE.format(
            title=title,
            date=date_str,
            toc=toc_html,
            body=body_html,
        )

        self._exports_count += 1
        logger.info("Exported HTML report %r (%d chars)", title, len(html))
        return html

    # ── Summarization ────────────────────────────────────────────

    async def summarize(self, text: str, max_length: int = 500) -> str:
        """Summarize text using the LLM.

        Args:
            text: The text to summarize.
            max_length: Approximate maximum character length for the summary.

        Returns:
            A concise summary string.
        """
        prompt = (
            f"Summarize the following text in at most {max_length} characters. "
            f"Capture the essential information.\n\n"
            f"--- TEXT ---\n\n{text}"
        )

        try:
            summary = await self._llm_complete(
                system=_SUMMARIZE_SYSTEM,
                user_content=prompt,
                model_tier="fast",
                max_tokens=max(300, max_length // 3),
            )
        except Exception as exc:
            logger.error("Summarization failed: %s", exc)
            # Fallback: naive truncation
            words = text.split()
            approx_words = max_length // 5
            summary = " ".join(words[:approx_words])
            if len(words) > approx_words:
                summary += "..."

        self._summaries_count += 1
        logger.info("Summarized %d-char text to %d chars", len(text), len(summary))
        return summary

    # ── Entity Extraction ────────────────────────────────────────

    async def extract_entities(self, text: str) -> dict:
        """Extract named entities from text.

        Returns:
            Dict with keys: companies, people, dates, numbers,
            currencies, percentages, tickers. Each maps to a list.
        """
        empty_result = {
            "companies": [],
            "people": [],
            "dates": [],
            "numbers": [],
            "currencies": [],
            "percentages": [],
            "tickers": [],
        }

        try:
            raw = await self._llm_complete(
                system=_ENTITY_SYSTEM,
                user_content=f"Extract entities from:\n\n{text}",
                model_tier="fast",
                max_tokens=1500,
            )
            data = _parse_json_response(raw)
        except Exception as exc:
            logger.error("Entity extraction failed: %s", exc)
            return empty_result

        # Merge with defaults to ensure all keys present
        for key in empty_result:
            if key not in data:
                data[key] = []
            elif not isinstance(data[key], list):
                data[key] = [data[key]]

        self._entities_extracted += 1
        total = sum(len(v) for v in data.values())
        logger.info("Extracted %d entities from %d-char text", total, len(text))
        return data

    # ── Document Comparison ──────────────────────────────────────

    async def compare_documents(self, doc_a: str, doc_b: str) -> dict:
        """Compare two documents for similarities and differences.

        Args:
            doc_a: First document text.
            doc_b: Second document text.

        Returns:
            Dict with keys: similarities, differences, unique_to_a,
            unique_to_b, overall_assessment.
        """
        prompt = (
            f"--- DOCUMENT A ({len(doc_a.split())} words) ---\n\n"
            f"{doc_a}\n\n"
            f"--- DOCUMENT B ({len(doc_b.split())} words) ---\n\n"
            f"{doc_b}"
        )

        empty_result = {
            "similarities": [],
            "differences": [],
            "unique_to_a": [],
            "unique_to_b": [],
            "overall_assessment": "Comparison failed.",
        }

        try:
            raw = await self._llm_complete(
                system=_COMPARE_SYSTEM,
                user_content=prompt,
                model_tier="default",
                max_tokens=2500,
            )
            data = _parse_json_response(raw)
        except Exception as exc:
            logger.error("Document comparison failed: %s", exc)
            return empty_result

        # Ensure all keys
        for key in ("similarities", "differences", "unique_to_a", "unique_to_b"):
            if key not in data:
                data[key] = []
        if "overall_assessment" not in data:
            data["overall_assessment"] = ""

        self._comparisons_count += 1
        logger.info(
            "Compared documents: %d similarities, %d differences",
            len(data.get("similarities", [])),
            len(data.get("differences", [])),
        )
        return data

    # ── Topic Study ──────────────────────────────────────────────

    async def study_topic(
        self, topic: str, depth: str = "standard"
    ) -> StudyResult:
        """Comprehensive study of a topic.

        Breaks the topic into subtopics, analyzes each, then synthesizes
        all findings. Stores everything in memory.

        Args:
            topic: The topic to study.
            depth: Study depth — "surface", "standard", or "deep".

        Returns:
            StudyResult with subtopics, findings, and synthesis.
        """
        if depth not in ("surface", "standard", "deep"):
            logger.warning("Unknown depth %r, defaulting to 'standard'", depth)
            depth = "standard"

        logger.info("Starting %s study of topic: %s", depth, topic)

        # Step 1: Break into subtopics
        try:
            raw = await self._llm_complete(
                system=_STUDY_SYSTEM,
                user_content=f"Topic: {topic}\nDepth: {depth}",
                model_tier="default",
                max_tokens=1500,
            )
            breakdown = _parse_json_response(raw)
        except Exception as exc:
            logger.error("Topic breakdown failed: %s", exc)
            return StudyResult(
                topic=topic,
                subtopics=(),
                findings=(f"Study failed during topic breakdown: {exc}",),
                synthesis="",
                knowledge_stored=0,
                sources_consulted=0,
            )

        subtopics = breakdown.get("subtopics", [])
        key_questions = breakdown.get("key_questions", [])

        if not subtopics:
            logger.warning("No subtopics generated for %r", topic)
            return StudyResult(
                topic=topic,
                subtopics=(),
                findings=("No subtopics could be identified.",),
                synthesis="",
                knowledge_stored=0,
                sources_consulted=0,
            )

        # Step 2: Analyze each subtopic
        all_findings: list[str] = []
        knowledge_stored = 0

        for i, subtopic in enumerate(subtopics):
            question = key_questions[i] if i < len(key_questions) else f"What is important about {subtopic}?"
            logger.info("Studying subtopic %d/%d: %s", i + 1, len(subtopics), subtopic)

            try:
                finding_raw = await self._llm_complete(
                    system=(
                        f"You are ROOT's research module studying '{topic}'. "
                        f"Provide a thorough analysis of this subtopic. "
                        f"Be factual, specific, and insightful. "
                        f"Return a concise but comprehensive paragraph."
                    ),
                    user_content=(
                        f"Subtopic: {subtopic}\n"
                        f"Key question: {question}\n\n"
                        f"Provide your analysis."
                    ),
                    model_tier="default",
                    max_tokens=800,
                )
                all_findings.append(f"[{subtopic}] {finding_raw}")

                # Store each finding in memory
                await self._store_memory(
                    f"Study of '{topic}' — {subtopic}: {finding_raw[:500]}",
                    ["study", topic.lower().replace(" ", "_"), "subtopic"],
                )
                knowledge_stored += 1

            except Exception as exc:
                logger.warning("Failed to study subtopic %r: %s", subtopic, exc)
                all_findings.append(f"[{subtopic}] Analysis failed: {exc}")

        # Step 3: Synthesize all findings
        synthesis = ""
        try:
            synth_raw = await self._llm_complete(
                system=_STUDY_SYNTHESIZE_SYSTEM,
                user_content=(
                    f"Topic: {topic}\n"
                    f"Depth: {depth}\n\n"
                    f"Findings from subtopic analysis:\n\n"
                    + "\n\n".join(all_findings)
                ),
                model_tier="default",
                max_tokens=2000,
            )
            synth_data = _parse_json_response(synth_raw)
            synthesis = synth_data.get("synthesis", "")
            extra_findings = synth_data.get("key_findings", [])
            if extra_findings:
                all_findings.extend(extra_findings)

            # Store synthesis in memory
            await self._store_memory(
                f"Study synthesis — '{topic}': {synthesis[:500]}",
                ["study", topic.lower().replace(" ", "_"), "synthesis"],
            )
            knowledge_stored += 1

        except Exception as exc:
            logger.error("Synthesis failed: %s", exc)
            synthesis = "Synthesis could not be completed."

        result = StudyResult(
            topic=topic,
            subtopics=tuple(subtopics),
            findings=tuple(all_findings),
            synthesis=synthesis,
            knowledge_stored=knowledge_stored,
            sources_consulted=len(subtopics),
        )

        self._studies_count += 1
        logger.info(
            "Completed %s study of %r: %d subtopics, %d findings, %d stored",
            depth,
            topic,
            len(result.subtopics),
            len(result.findings),
            result.knowledge_stored,
        )

        return result

    # ── Stats ────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return engine statistics."""
        return {
            "analyses_count": self._analyses_count,
            "reports_generated": self._reports_generated,
            "exports_count": self._exports_count,
            "entities_extracted": self._entities_extracted,
            "comparisons_count": self._comparisons_count,
            "studies_count": self._studies_count,
            "summaries_count": self._summaries_count,
            "has_llm": self._llm is not None,
            "has_memory": self._memory is not None,
        }
