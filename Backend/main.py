from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(
    title="Tutu Backend API",
    description="Local MVP backend for the Tutu voice companion.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatResponse(BaseModel):
    user_text: str
    reply_text: str
    audio_url: str | None
    voice: str
    mode: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def parse_history(history: str) -> list[dict[str, Any]]:
    if not history:
        return []

    try:
        parsed = json.loads(history)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="history must be valid JSON") from exc

    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="history must be a JSON array")

    return parsed


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    audio: UploadFile = File(...),
    voice: str = Form("female"),
    history: str = Form("[]"),
) -> ChatResponse:
    parse_history(history)

    if voice not in {"female", "male"}:
        raise HTTPException(status_code=400, detail="voice must be 'female' or 'male'")

    if not audio.filename:
        raise HTTPException(status_code=400, detail="audio file is required")

    # MVP stage: keep the interface stable for APP/ESP32 integration first.
    # Replace this block with ASR -> LLM -> TTS after B can call the endpoint.
    return ChatResponse(
        user_text="我最近有点迷茫，不知道该找什么工作。",
        reply_text="听起来你现在有些不确定。我们可以先从你的兴趣、专业和想要的生活方式开始梳理。",
        audio_url=None,
        voice=voice,
        mode="mock",
    )
