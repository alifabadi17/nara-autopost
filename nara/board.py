"""Papan mix & match otomatis dari foto produk (tanpa model). Satu papan = satu acara."""
from pathlib import Path

W, H = 1080, 1350
BG = (244, 239, 231)        # krem hangat
CARD = (255, 255, 255)
INK = (38, 32, 28)
MUTED = (120, 108, 98)
ACCENT = (150, 98, 64)      # cokelat karamel
FONTS = {
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    "reg": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf"],
}


def _font(kind, size):
    from PIL import ImageFont
    for p in FONTS[kind]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def _rupiah(n):
    return "Rp" + f"{int(n):,}".replace(",", ".") if n else ""


def _fit(img, box_w, box_h):
    """Perkecil gambar agar muat utuh di kotak (tidak dipotong), lalu tengahkan di kanvas putih."""
    from PIL import Image
    img = img.convert("RGB")
    img.thumbnail((box_w, box_h), Image.LANCZOS)
    canvas = Image.new("RGB", (box_w, box_h), CARD)
    canvas.paste(img, ((box_w - img.width) // 2, (box_h - img.height) // 2))
    return canvas


def _wrap(draw, text, font, width, max_lines=2):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= width:
            cur = test
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if len(lines) == max_lines and draw.textlength(lines[-1], font=font) > width:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines[:max_lines]


def _card(sheet, draw, x, y, w, h, item, root):
    from PIL import Image
    label_h = 92
    sheet.paste(Image.new("RGB", (w, h), CARD), (x, y))
    pic = Image.open(Path(root) / item["image"])
    sheet.paste(_fit(pic, w - 24, h - label_h - 24), (x + 12, y + 12))
    name_f, price_f = _font("bold", 26), _font("reg", 24)
    ty = y + h - label_h + 6
    for line in _wrap(draw, item["name"], name_f, w - 28, 1):
        draw.text((x + 14, ty), line, font=name_f, fill=INK)
        ty += 34
    draw.text((x + 14, ty), _rupiah(item.get("price")), font=price_f, fill=ACCENT)


def render_board(board, root, step=None, total=None):
    """board = {"title": "NGANTOR", "subtitle": "...", "items": [{"name","price","image"}, ...]}.
    Item pertama = item utama (besar di kiri). Mengembalikan PIL.Image 1080x1350."""
    from PIL import Image, ImageDraw
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    m = 48
    tag = f"{step}/{total}  " if step and total else ""
    d.text((m, 44), (tag + "1 ITEM 3 ACARA").upper(), font=_font("bold", 30), fill=ACCENT)
    d.text((m, 88), board["title"].upper(), font=_font("bold", 64), fill=INK)
    if board.get("subtitle"):
        d.text((m, 168), board["subtitle"], font=_font("reg", 30), fill=MUTED)
    top, gap = 232, 20
    bottom = H - 76
    items = board["items"][:4]
    n = len(items)
    cols = 1 if n == 1 else 2
    rows = (n + cols - 1) // cols
    cw = (W - 2 * m - gap * (cols - 1)) // cols
    ch = (bottom - top - gap * (rows - 1)) // rows
    for i, it in enumerate(items):
        x = m + (i % cols) * (cw + gap)
        y = top + (i // cols) * (ch + gap)
        _card(sheet, d, x, y, cw, ch, it, root)
        if i == 0 and n > 1:
            d.rectangle([x, y, x + cw - 1, y + ch - 1], outline=ACCENT, width=4)
            tf = _font("bold", 22)
            label = "ITEM UTAMA"
            tw = d.textlength(label, font=tf)
            d.rectangle([x, y, x + tw + 28, y + 40], fill=ACCENT)
            d.text((x + 14, y + 8), label, font=tf, fill=(255, 255, 255))
    d.text((m, H - 52), "Link semua item ada di balasan", font=_font("reg", 26), fill=MUTED)
    return sheet


def run_boards(posts, root, save_post, log=print):
    """Buat gambar papan untuk draft yang punya 'boards' dan gambarnya belum ada."""
    root = Path(root)
    made = 0
    for post in posts:
        if post.get("status", "draft") != "draft" or not post.get("boards"):
            continue
        boards = post["boards"]
        paths = [f"images/{post['id']}-{i + 1}.jpg" for i in range(len(boards))]
        missing = [i for i, p in enumerate(paths) if not (root / p).exists()]
        if not missing:
            if post.get("images") != paths:
                post["images"] = paths
                save_post(post)
            continue
        for i in missing:
            try:
                img = render_board(boards[i], root, i + 1, len(boards))
            except Exception as e:  # noqa: BLE001
                post["image_error"] = f"papan {i + 1}: {e}"[:300]
                save_post(post)
                log(f"{post['id']}: gagal membuat papan: {e}")
                break
            out = root / paths[i]
            out.parent.mkdir(parents=True, exist_ok=True)
            img.save(out, "JPEG", quality=92)
            made += 1
            log(f"{post['id']}: papan {i + 1} -> {paths[i]}")
        else:
            post["images"] = paths
            post.pop("image_error", None)
            post["image_source"] = "board"
            save_post(post)
    return made
