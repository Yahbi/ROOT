"""Chat routes — Yohan talks to ROOT here, with ASTRA-supervised agent dispatch."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("root.routes.chat")

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Directory for uploaded files
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Max file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Supported text-based file types
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".java", ".go", ".rs", ".rb", ".php", ".sh", ".bash",
    ".sql", ".env", ".toml", ".ini", ".cfg", ".conf",
    ".log", ".dockerfile", ".makefile", ".gitignore",
    ".r", ".swift", ".kt", ".scala", ".c", ".cpp", ".h",
}


class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    file_context: Optional[str] = None  # Injected file content for agents
    model_tier: Optional[str] = None    # Override LLM tier: fast/default/thinking


class RememberRequest(BaseModel):
    content: str
    memory_type: str = "fact"
    tags: Optional[list[str]] = None


class FeedbackRequest(BaseModel):
    message_index: int
    feedback: str


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    message: str = Form(""),
):
    """Upload a file and chat about it — agents read and learn from the content."""
    brain = request.app.state.brain

    # Validate size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large ({len(contents)} bytes). Max: {MAX_FILE_SIZE // 1024 // 1024}MB")

    # Save file
    ext = Path(file.filename or "file").suffix.lower()
    safe_name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename or 'file').name}"
    file_path = UPLOAD_DIR / safe_name
    file_path.write_bytes(contents)

    # Extract text content
    file_text = ""
    if ext in TEXT_EXTENSIONS or ext == "":
        try:
            file_text = contents.decode("utf-8", errors="replace")
        except Exception:
            file_text = contents.decode("latin-1", errors="replace")
    elif ext == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=contents, filetype="pdf")
            file_text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
        except ImportError:
            file_text = "[PDF reading requires PyMuPDF — install with: pip install pymupdf]"
        except Exception as e:
            file_text = f"[Error reading PDF: {e}]"
    else:
        # Try as text anyway
        try:
            file_text = contents.decode("utf-8", errors="replace")
        except Exception:
            file_text = f"[Binary file: {file.filename}, {len(contents)} bytes — cannot extract text]"

    # Truncate to 50K chars for context window
    truncated = len(file_text) > 50000
    file_text = file_text[:50000]

    # Build the message with file context
    user_msg = message.strip() if message.strip() else f"I've uploaded a file: {file.filename}. Read it, learn from it, and tell me what's in it."
    file_context = (
        f"\n\n---\n## Attached File: {file.filename}\n"
        f"**Size**: {len(contents):,} bytes | **Type**: {ext or 'unknown'}"
        f"{' | **Truncated**: yes (showing first 50K chars)' if truncated else ''}\n"
        f"```\n{file_text}\n```\n---"
    )

    # Send to brain with file context injected
    full_message = user_msg + file_context
    response = await brain.chat(full_message)
    data = response.model_dump()

    # Track file upload activity
    user_patterns = getattr(request.app.state, "user_patterns", None)
    if user_patterns:
        try:
            user_patterns.record_activity(
                message=user_msg,
                topic=f"file_upload:{ext}",
                intent="upload",
            )
        except Exception as exc:
            logger.warning("Failed to record user pattern for file upload: %s", exc)

    # Add file metadata to response
    data["file"] = {
        "filename": file.filename,
        "size": len(contents),
        "type": ext,
        "path": str(file_path),
        "truncated": truncated,
        "chars_extracted": len(file_text),
    }

    # Store file knowledge in memory
    memory = request.app.state.memory
    from backend.models.memory import MemoryEntry, MemoryType
    memory.store(MemoryEntry(
        content=f"File uploaded: {file.filename} ({len(contents):,} bytes, {ext}). Content preview: {file_text[:300]}",
        memory_type=MemoryType.FACT,
        tags=["file_upload", ext.lstrip(".") or "text", file.filename or "unknown"],
        source="file_upload",
        confidence=1.0,
    ))

    # Flatten agent_findings
    if data.get("agent_findings"):
        data["agent_findings"] = [
            {
                "agent_id": f.get("agent_id", "unknown"),
                "agent_name": f.get("agent_name", "unknown"),
                "task": f.get("task", ""),
                "result": f.get("result", "")[:2000],
                "status": f.get("status", "unknown"),
                "duration_seconds": f.get("duration_seconds", 0),
                "messages_exchanged": f.get("messages_exchanged", 0),
                "tools_executed": f.get("tools_executed", 0),
                "tools_used": f.get("tools_used", []),
            }
            for f in data["agent_findings"]
        ]

    return data


@router.post("")
async def chat(req: ChatRequest, request: Request):
    """Send a message to ROOT — ASTRA routes it to agents automatically."""
    brain = request.app.state.brain

    # Inject file context if provided
    msg = req.message
    if req.file_context:
        msg = msg + "\n\n---\n" + req.file_context + "\n---"

    response = await brain.chat(msg)
    data = response.model_dump()

    # Track user activity patterns
    user_patterns = getattr(request.app.state, "user_patterns", None)
    if user_patterns:
        try:
            user_patterns.record_activity(
                message=req.message,
                topic=data.get("routing_reasoning", "")[:200],
                intent=data.get("route", "direct"),
                agents_used=data.get("agents_used", []),
                response_quality=0.7 if data.get("agent_findings") else 0.5,
            )
        except Exception as exc:
            logger.warning("Failed to record user pattern: %s", exc)

    # Flatten agent_findings for frontend consumption
    if data.get("agent_findings"):
        data["agent_findings"] = [
            {
                "agent_id": f.get("agent_id", "unknown"),
                "agent_name": f.get("agent_name", "unknown"),
                "task": f.get("task", ""),
                "result": f.get("result", "")[:2000],  # Cap for transport
                "status": f.get("status", "unknown"),
                "duration_seconds": f.get("duration_seconds", 0),
                "messages_exchanged": f.get("messages_exchanged", 0),
                "tools_executed": f.get("tools_executed", 0),
                "tools_used": f.get("tools_used", []),
            }
            for f in data["agent_findings"]
        ]

    return data


@router.post("/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """Stream a chat response via Server-Sent Events.

    Returns SSE events as each step completes:
    - thinking: routing/synthesis stage indicator
    - routing: ASTRA routing decision
    - agent_start: agent task dispatched
    - agent_result: agent finding received
    - token: streaming text chunk
    - done: final complete response
    """
    brain = request.app.state.brain

    msg = req.message
    if req.file_context:
        msg = msg + "\n\n---\n" + req.file_context + "\n---"

    async def event_generator():
        async for event in brain.chat_stream(msg):
            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}), default=str)
            yield f"event: {event_type}\ndata: {data}\n\n"

    # Track user activity
    user_patterns = getattr(request.app.state, "user_patterns", None)
    if user_patterns:
        try:
            user_patterns.record_activity(
                message=req.message, topic="streaming", intent="chat_stream",
            )
        except Exception as exc:
            logger.warning("Pattern recording failed: %s", exc)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/remember")
async def remember(req: RememberRequest, request: Request):
    """Explicitly tell ROOT to remember something."""
    brain = request.app.state.brain
    entry = await brain.remember(req.content, req.memory_type, req.tags)
    return {"status": "stored", "memory": entry.model_dump()}


@router.post("/feedback")
async def feedback(req: FeedbackRequest, request: Request):
    """Give ROOT feedback on a response so it can learn."""
    brain = request.app.state.brain
    conversation = brain.get_conversation()

    if req.message_index < 0 or req.message_index >= len(conversation):
        raise HTTPException(status_code=422, detail="Invalid message index")

    idx = req.message_index
    user_msg = conversation[idx - 1]["content"] if idx > 0 else ""
    assistant_msg = conversation[idx]["content"]

    reflection = await request.app.state.reflection.reflect_on_interaction(
        user_msg, assistant_msg, req.feedback
    )

    # Feed feedback to learning engine — find the actual latest interaction ID
    learning = getattr(request.app.state, "learning", None)
    if learning:
        try:
            row = learning.conn.execute(
                "SELECT id FROM interactions ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if row:
                learning.record_user_feedback(row["id"], req.feedback)
        except Exception as exc:
            logger.warning("Failed to record feedback: %s", exc)

    return {
        "status": "reflected",
        "reflection": reflection.model_dump() if reflection else None,
    }


@router.get("/history")
async def history(request: Request):
    """Get current conversation history."""
    brain = request.app.state.brain
    return {"messages": brain.get_conversation()}


@router.post("/clear")
async def clear(request: Request):
    """Clear conversation history."""
    brain = request.app.state.brain
    brain.clear_conversation()
    return {"status": "cleared"}
