# Tutu Backend

Member C 的后端 MVP。接口对 APP 保持稳定，内部链路为：

```text
audio -> Qwen3-ASR-Flash -> Qwen3.6-Plus -> Qwen3-TTS-Flash
```

## 本地启动

```bash
cd Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

编辑 `.env`，填入百炼/DashScope API Key：

```env
DASHSCOPE_API_KEY=你的百炼APIKey
PUBLIC_BASE_URL=http://47.86.176.64
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
  "audio_url": "https://dashscope-result-.../xxx.wav",
  "voice": "female",
  "mode": "qwen"
}
```

`audio_url` 是 DashScope 返回的临时语音文件地址，通常有有效期限制，APP 应尽快下载或播放。

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

## 服务器更新

服务器已经部署后，更新代码：

```bash
cd /root/Tutu
git pull origin main
cd Backend
source .venv/bin/activate
pip install -r requirements.txt
systemctl restart tutu-backend
```
