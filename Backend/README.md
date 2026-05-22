# Tutu Backend

Member C 的本地后端 MVP。当前版本先固定接口格式，返回 mock 数据，方便 Member B 先联调 APP 到云端的请求链路。

## 本地启动

```bash
cd Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：

```text
GET http://127.0.0.1:8000/health
```

期望返回：

```json
{"status":"ok"}
```

## 聊天接口

```text
POST /api/chat
Content-Type: multipart/form-data
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| audio | file | 是 | 用户录音文件，建议先用 wav/m4a/mp3 |
| voice | string | 否 | `female` 或 `male`，默认 `female` |
| history | string | 否 | JSON 字符串数组，默认 `[]` |

返回：

```json
{
  "user_text": "用户语音识别出的文字",
  "reply_text": "AI 回复文字",
  "audio_url": null,
  "voice": "female",
  "mode": "mock"
}
```

## 本地测试命令

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -F "audio=@sample.wav" \
  -F "voice=female" \
  -F 'history=[]'
```

## 下一步

等 Member B 确认接口能调通后，再把 `main.py` 中的 mock 逻辑替换为：

```text
audio -> Whisper ASR -> GPT 回复 -> TTS 生成语音 -> 返回文本和音频地址
```
