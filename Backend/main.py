from __future__ import annotations

import base64
import json
import mimetypes
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, OpenAIError
from pydantic import BaseModel


load_dotenv()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
DASHSCOPE_TTS_URL = os.getenv(
    "DASHSCOPE_TTS_URL",
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
)

ASR_MODEL = os.getenv("QWEN_ASR_MODEL", "qwen3-asr-flash")
CHAT_MODEL = os.getenv("QWEN_CHAT_MODEL", "qwen3.6-plus")
TTS_MODEL = os.getenv("QWEN_TTS_MODEL", "qwen3-tts-flash")

VOICE_MAP = {
    "female": os.getenv("QWEN_TTS_FEMALE_VOICE", "Cherry"),
    "male": os.getenv("QWEN_TTS_MALE_VOICE", "Ethan"),
}

SYSTEM_PROMPT = os.getenv(
    "TUTU_SYSTEM_PROMPT",
    (
        "你是一个集招聘专家、培养方案专家、心理咨询师于一身的智能玩偶。"
        "回答时遵循：1. 招聘和职业建议要务实、具体；"
        "2. 心理支持要有共情心，但不能替代专业医疗诊断；"
        "3. 回答要口语化、简短，适合用语音播放；"
        "4. 每次回复控制在 80 字以内。"
    ),
)

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


def require_dashscope_key() -> None:
    if not DASHSCOPE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="DASHSCOPE_API_KEY is not configured on the backend server",
        )


def get_dashscope_client() -> OpenAI:
    require_dashscope_key()
    return OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)


def audio_to_data_url(
    audio_bytes: bytes,
    content_type: str | None,
    filename: str | None,
) -> str:
    guessed_type = mimetypes.guess_type(filename or "")[0]
    media_type = guessed_type or content_type or "audio/wav"
    if media_type == "application/octet-stream":
        media_type = guessed_type or "audio/wav"
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def history_to_messages(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    for item in history[-8:]:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        messages.append({"role": role, "content": content})

    return messages


def transcribe_audio(
    audio_bytes: bytes,
    content_type: str | None,
    filename: str | None,
) -> str:
    data_url = audio_to_data_url(audio_bytes, content_type, filename)
    dashscope_client = get_dashscope_client()

    try:
        response = dashscope_client.chat.completions.create(
            model=ASR_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": data_url},
                        }
                    ],
                }
            ],
            extra_body={"asr_options": {"enable_itn": False}},
        )
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=f"ASR request failed: {exc}") from exc

    text = response.choices[0].message.content
    if not text:
        raise HTTPException(status_code=502, detail="ASR returned empty text")

    return text.strip()


def generate_reply(user_text: str, history: list[dict[str, Any]]) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history_to_messages(history))
    messages.append({"role": "user", "content": user_text})
    dashscope_client = get_dashscope_client()

    try:
        response = dashscope_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=180,
        )
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    text = response.choices[0].message.content
    if not text:
        raise HTTPException(status_code=502, detail="LLM returned empty text")

    return text.strip()


async def synthesize_speech(reply_text: str, voice: str) -> str:
    payload = {
        "model": TTS_MODEL,
        "input": {
            "text": reply_text,
            "voice": VOICE_MAP[voice],
            "language_type": "Chinese",
        },
    }
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as http_client:
            response = await http_client.post(
                DASHSCOPE_TTS_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"TTS request failed: {exc}") from exc

    data = response.json()
    audio_url = data.get("output", {}).get("audio", {}).get("url")
    if not audio_url:
        raise HTTPException(status_code=502, detail=f"TTS returned no audio url: {data}")

    return audio_url


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    audio: UploadFile = File(...),
    voice: str = Form("female"),
    history: str = Form("[]"),
) -> ChatResponse:
    require_dashscope_key()
    parsed_history = parse_history(history)

    if voice not in {"female", "male"}:
        raise HTTPException(status_code=400, detail="voice must be 'female' or 'male'")

    if not audio.filename:
        raise HTTPException(status_code=400, detail="audio file is required")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="audio file is empty")

    user_text = transcribe_audio(audio_bytes, audio.content_type, audio.filename)
    reply_text = generate_reply(user_text, parsed_history)
    audio_url = await synthesize_speech(reply_text, voice)

    return ChatResponse(
        user_text=user_text,
        reply_text=reply_text,
        audio_url=audio_url,
        voice=voice,
        mode="qwen",
    )
