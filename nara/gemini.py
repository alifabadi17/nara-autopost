"""Pembuat gambar Nara lewat Gemini API (pustaka standar saja)."""
import base64
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(Exception):
    pass


def _call(method, path, key, body=None, timeout=180):
    url = f"{API}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("x-goog-api-key", key)  # kunci lewat header, tidak pernah di URL/log
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise GeminiError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:600]}") from None
    except urllib.error.URLError as e:
        raise GeminiError(f"Koneksi gagal: {e.reason}") from None


def image_models(key):
    """Daftar model yang namanya mengandung 'image' dan mendukung generateContent, terbaru dulu."""
    out, token = [], None
    while True:
        q = "models?pageSize=200" + (f"&pageToken={urllib.parse.quote(token)}" if token else "")
        data = _call("GET", q, key)
        for m in data.get("models", []):
            name = m.get("name", "")
            if "image" in name and "generateContent" in m.get("supportedGenerationMethods", []) \
                    and "imagen" not in name:
                out.append(name.split("/", 1)[1])
        token = data.get("nextPageToken")
        if not token:
            break
    return sorted(out, reverse=True)


def _inline(path):
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(Path(path).read_bytes()).decode()}}


def generate_image(key, model, prompt, refs=(), aspect_ratio="4:5"):
    """Kembalikan (bytes, mime). refs = path gambar referensi wajah/gaya Nara."""
    parts = [{"text": prompt}] + [_inline(p) for p in refs]
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}
    if aspect_ratio:
        body["generationConfig"]["imageConfig"] = {"aspectRatio": aspect_ratio}
    try:
        data = _call("POST", f"models/{model}:generateContent", key, body)
    except GeminiError as e:
        if aspect_ratio and "HTTP 400" in str(e):
            return generate_image(key, model, prompt, refs, aspect_ratio=None)
        raise
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                return base64.b64decode(blob["data"]), blob.get("mimeType") or blob.get("mime_type")
    reason = (data.get("candidates") or [{}])[0].get("finishReason") or data.get("promptFeedback")
    raise GeminiError(f"Tidak ada gambar di respons (alasan: {reason})")
