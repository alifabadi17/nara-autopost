"""Tempel watermark teks di pojok kanan bawah gambar.

Metadata asli file (EXIF/XMP/tanda asal-usul C2PA) disalin kembali ke file hasil,
jadi watermark tidak menghapus informasi asal gambar.
"""
import hashlib
import io
import json
import struct
from pathlib import Path

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
MANIFEST = ".watermarked.json"
PNG_SIG = b"\x89PNG\r\n\x1a\n"
PNG_KEEP = {b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"caBX"}
JPEG_KEEP = {0xE1, 0xEB}  # APP1 (EXIF/XMP), APP11 (C2PA/JUMBF)


def _font(size):
    from PIL import ImageFont
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _draw(img, text):
    from PIL import Image, ImageDraw
    base = img.convert("RGBA")
    w, h = base.size
    size = max(18, int(min(w, h) * 0.035))
    font = _font(size)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    left, top, right, bottom = d.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top
    x, y = w - tw - size, h - th - size - top
    off = max(1, size // 14)
    region = base.crop((max(0, int(x)), max(0, int(y)), min(w, int(x + tw)), min(h, int(y + th + top + off)))).convert("L")
    hist = region.histogram()
    total = sum(hist) or 1
    lum = sum(i * c for i, c in enumerate(hist)) / total
    if lum > 150:   # latar terang -> tulisan gelap
        d.text((x + off, y + off), text, font=font, fill=(255, 255, 255, 120))
        d.text((x, y), text, font=font, fill=(40, 32, 28, 200))
    else:           # latar gelap -> tulisan putih
        d.text((x + off, y + off), text, font=font, fill=(0, 0, 0, 110))
        d.text((x, y), text, font=font, fill=(255, 255, 255, 215))
    return Image.alpha_composite(base, overlay)


def _jpeg_segments(data, keep):
    """Ambil segmen APP yang dipertahankan dari JPEG (sebelum SOS)."""
    out, i = [], 2
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker == 0xDA:  # SOS
            break
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in keep:
            out.append(data[i:i + 2 + length])
        i += 2 + length
    return out


def _jpeg_insert(data, segments):
    pos = 2
    if data[2:4] == b"\xff\xe0":  # lewati APP0 JFIF
        pos = 4 + struct.unpack(">H", data[4:6])[0]
    return data[:pos] + b"".join(segments) + data[pos:]


def _png_chunks(data):
    i = len(PNG_SIG)
    while i < len(data):
        length = struct.unpack(">I", data[i:i + 4])[0]
        ctype = data[i + 4:i + 8]
        yield ctype, data[i:i + 12 + length]
        i += 12 + length


def _png_merge(original, new):
    keep = [raw for ctype, raw in _png_chunks(original) if ctype in PNG_KEEP]
    present = {raw for ctype, raw in _png_chunks(new) if ctype in PNG_KEEP}
    keep = [k for k in keep if k not in present]
    out, inserted = [PNG_SIG], False
    for ctype, raw in _png_chunks(new):
        if ctype == b"IDAT" and not inserted:
            out += keep
            inserted = True
        out.append(raw)
    return b"".join(out)


def watermark_bytes(data, text):
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    fmt = (img.format or "").upper()
    icc = img.info.get("icc_profile")
    marked = _draw(img, text)
    buf = io.BytesIO()
    if fmt == "PNG":
        marked.save(buf, "PNG", icc_profile=icc, optimize=True)
        return _png_merge(data, buf.getvalue())
    marked.convert("RGB").save(buf, "JPEG", quality=92, icc_profile=icc)
    return _jpeg_insert(buf.getvalue(), _jpeg_segments(data, JPEG_KEEP))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_manifest(images_dir):
    p = Path(images_dir) / MANIFEST
    return json.loads(p.read_text()) if p.exists() else {}


def is_watermarked(path):
    path = Path(path)
    return load_manifest(path.parent).get(path.name) == sha(path.read_bytes())


def process_dir(images_dir, text, log=print):
    images_dir = Path(images_dir)
    manifest = load_manifest(images_dir)
    done = 0
    for p in sorted(images_dir.iterdir()):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png") or not p.is_file():
            continue
        data = p.read_bytes()
        if manifest.get(p.name) == sha(data):
            continue
        out = watermark_bytes(data, text)
        p.write_bytes(out)
        manifest[p.name] = sha(out)
        done += 1
        log(f"watermark: {p.name}")
    if done:
        (images_dir / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return done
