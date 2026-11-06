"""Antrean, persetujuan lewat GitHub Issue, dan logika posting."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = REPO_ROOT / "queue"
MAX_CHARS = 500
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_EXT = {".jpg", ".jpeg", ".png"}
ISSUE_TITLE = "Antrean Nara: centang untuk menyetujui"
CHECK_RE = re.compile(r"^- \[([ xX])\] `([^`]+)`", re.MULTILINE)
HARI = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def load_config():
    return json.loads((REPO_ROOT / "config.json").read_text(encoding="utf-8"))


def local_tz(cfg):
    return timezone(timedelta(hours=cfg.get("timezone_offset_hours", 8)))


def parse_time(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"scheduled_at harus punya zona waktu, mis. +08:00: {value}")
    return dt


def fmt_local(dt, cfg):
    d = dt.astimezone(local_tz(cfg))
    return f"{HARI[d.weekday()]} {d.day} {BULAN[d.month - 1]} {d:%H:%M} {cfg.get('timezone_label', '')}".strip()


# ---------- antrean ----------

def load_posts(queue_dir=None):
    queue_dir = Path(queue_dir or QUEUE_DIR)
    posts = []
    for path in sorted(queue_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_path"] = path
        posts.append(data)
    return posts


def save_post(post):
    path = post["_path"]
    clean = {k: v for k, v in post.items() if not k.startswith("_")}
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def final_texts(post, cfg):
    """Teks utama + balasan setelah label wajib ditambahkan otomatis."""
    text = (post.get("text") or "").strip()
    reply = (post.get("reply_text") or "").strip()
    label_ai = cfg.get("label_ai")
    if post.get("images") and post.get("ai_image", True) and label_ai and label_ai.lower() not in text.lower():
        text = f"{text}\n\n{label_ai}"
    label_aff = cfg.get("label_affiliate")
    if reply and label_aff and ("http" in reply or "shopee" in reply.lower()) \
            and "afiliasi" not in reply.lower() and "affiliate" not in reply.lower():
        reply = f"{reply}\n\n{label_aff}"
    return text, reply


def image_problems(post, root=None):
    root = Path(root or REPO_ROOT)
    problems = []
    for rel in post.get("images") or []:
        p = root / rel
        if p.suffix.lower() not in IMAGE_EXT:
            problems.append(f"{rel}: format harus JPG/PNG")
        elif not p.exists():
            problems.append(f"{rel}: belum diunggah")
        elif p.stat().st_size > MAX_IMAGE_BYTES:
            problems.append(f"{rel}: lebih dari 8 MB")
    return problems


def validate(post, cfg, root=None):
    problems = []
    for key in ("id", "scheduled_at", "text"):
        if not post.get(key):
            problems.append(f"kolom '{key}' wajib diisi")
    if post.get("scheduled_at"):
        try:
            parse_time(post["scheduled_at"])
        except ValueError as e:
            problems.append(str(e))
    if len(post.get("images") or []) > 10:
        problems.append("maksimal 10 gambar")
    text, reply = final_texts(post, cfg)
    if len(text) > MAX_CHARS:
        problems.append(f"teks utama {len(text)} karakter (maks {MAX_CHARS}, sudah termasuk label)")
    if len(reply) > MAX_CHARS:
        problems.append(f"teks balasan {len(reply)} karakter (maks {MAX_CHARS})")
    if post.get("id") and post["_path"].stem != post["id"]:
        problems.append(f"nama file harus {post['id']}.json")
    return problems


# ---------- persetujuan ----------

def parse_checked(body):
    return {m.group(2) for m in CHECK_RE.finditer(body or "") if m.group(1) in "xX"}


def render_issue(drafts, checked, cfg, root=None):
    lines = [
        "Centang kotak di depan postingan yang **disetujui**. Sistem akan memostingnya otomatis "
        "pada jadwalnya (dicek tiap ±15 menit). Yang tidak dicentang tidak akan pernah diposting.",
        "",
        "Gambar diunggah ke folder `images/` dengan nama persis seperti di daftar. "
        "Postingan yang gambarnya belum ada akan ditunda sampai gambarnya ada.",
        "",
    ]
    if not drafts:
        lines.append("_Antrean kosong._")
    for post in drafts:
        mark = "x" if post["id"] in checked else " "
        when = fmt_local(parse_time(post["scheduled_at"]), cfg) if post.get("scheduled_at") else "?"
        first = (post.get("text") or "").strip().splitlines()[0][:70] if post.get("text") else ""
        status = []
        img_probs = image_problems(post, root)
        if post.get("images"):
            status.append("gambar belum lengkap" if img_probs else "gambar siap")
        probs = validate(post, cfg, root)
        if probs:
            status.append("perlu diperbaiki")
        if post.get("last_error"):
            status.append(f"gagal {post.get('attempts', 0)}x")
        tag = f" ({', '.join(status)})" if status else ""
        lines.append(f"- [{mark}] `{post['id']}` | **{when}** | {first}{tag}")
        text, reply = final_texts(post, cfg)
        detail = ["", "<details><summary>Lihat isi</summary>", "", "**Postingan utama**", "", "```text",
                  text, "```"]
        if reply:
            detail += ["", "**Balasan (utas kedua)**", "", "```text", reply, "```"]
        if post.get("images"):
            detail += ["", "**Gambar**", ""]
            for rel in post["images"]:
                ok = (Path(root or REPO_ROOT) / rel).exists()
                detail.append(f"- {'ada' if ok else 'BELUM ADA'}: `{rel}`")
        if post.get("image_prompt"):
            detail += ["", "**Prompt untuk Gem Nara Photo Studio**", "", "```text", post["image_prompt"], "```"]
        if probs:
            detail += ["", "**Masalah:** " + "; ".join(probs)]
        if post.get("last_error"):
            detail += ["", f"**Error terakhir:** {post['last_error']}"]
        detail += ["", "</details>", ""]
        lines += detail
    return "\n".join(lines).rstrip() + "\n"


def pending(posts):
    def key(p):
        try:
            return parse_time(p["scheduled_at"])
        except Exception:
            return datetime.max.replace(tzinfo=timezone.utc)
    return sorted([p for p in posts if p.get("status", "draft") == "draft"], key=key)


def sync_issue(gh, posts, cfg, root=None):
    """Perbarui issue antrean (tanpa menghapus centang) dan kembalikan (nomor_issue, id_disetujui)."""
    gh.ensure_label()
    issue = gh.find_queue_issue()
    checked = parse_checked(issue["body"]) if issue else set()
    drafts = pending(posts)
    body = render_issue(drafts, checked, cfg, root)
    if issue is None:
        issue = gh.create_issue(ISSUE_TITLE, body)
    elif (issue.get("body") or "").strip() != body.strip():
        # Baca ulang sesaat sebelum menulis agar centang yang baru masuk tidak hilang.
        latest = gh.find_queue_issue()
        checked |= parse_checked(latest["body"]) if latest else set()
        body = render_issue(drafts, checked, cfg, root)
        gh.update_issue_body(issue["number"], body)
    return issue["number"], checked


# ---------- posting ----------

def raw_url(rel_path):
    repo = os.environ["GITHUB_REPOSITORY"]
    ref = os.environ.get("GITHUB_SHA") or "main"
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{rel_path}"


def run_posting(threads, posts, approved, cfg, now=None, root=None, url_for=raw_url, log=print):
    """Posting yang sudah disetujui dan sudah waktunya. Mengembalikan (terposting, error)."""
    now = now or datetime.now(timezone.utc)
    done, errors = [], []

    # 1) Lengkapi balasan yang sempat gagal pada postingan yang sudah terbit.
    for post in posts:
        if post.get("status") == "posted" and post.get("reply_text") and not post.get("reply_id") \
                and post.get("reply_attempts", 0) < cfg.get("max_attempts", 3):
            _, reply = final_texts(post, cfg)
            try:
                post["reply_id"] = threads.post(reply, reply_to_id=post["threads_id"])
                post.pop("reply_error", None)
            except Exception as e:  # noqa: BLE001
                post["reply_attempts"] = post.get("reply_attempts", 0) + 1
                post["reply_error"] = str(e)
                errors.append(f"{post['id']} (balasan): {e}")
            save_post(post)

    # 2) Postingan baru.
    budget = cfg.get("max_posts_per_run", 1)
    for post in pending(posts):
        if budget <= 0:
            break
        pid = post.get("id")
        if pid not in approved:
            continue
        if validate(post, cfg, root):
            continue
        if parse_time(post["scheduled_at"]) > now:
            continue
        if image_problems(post, root):
            log(f"{pid}: menunggu gambar")
            continue
        text, reply = final_texts(post, cfg)
        try:
            urls = [url_for(rel) for rel in post.get("images") or []]
            post["threads_id"] = threads.post(text, urls)
            post["status"] = "posted"
            post["posted_at"] = now.isoformat(timespec="seconds")
            post.pop("last_error", None)
            budget -= 1
            try:
                post["permalink"] = threads.permalink(post["threads_id"])
            except Exception:  # noqa: BLE001
                pass
            if reply:
                try:
                    post["reply_id"] = threads.post(reply, reply_to_id=post["threads_id"])
                except Exception as e:  # noqa: BLE001
                    post["reply_attempts"] = 1
                    post["reply_error"] = str(e)
                    errors.append(f"{pid} (balasan): {e}")
            done.append(post)
            log(f"{pid}: terposting {post.get('permalink', post['threads_id'])}")
        except Exception as e:  # noqa: BLE001
            post["attempts"] = post.get("attempts", 0) + 1
            post["last_error"] = str(e)
            if post["attempts"] >= cfg.get("max_attempts", 3):
                post["status"] = "failed"
            errors.append(f"{pid}: {e}")
        save_post(post)
    return done, errors


def run_insights(threads, posts, cfg, now=None):
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(days=cfg.get("insights_days", 14))
    updated = 0
    for post in posts:
        if post.get("status") != "posted" or not post.get("threads_id"):
            continue
        if datetime.fromisoformat(post["posted_at"]) < horizon:
            continue
        post["insights"] = threads.insights(post["threads_id"])
        post["insights_at"] = now.isoformat(timespec="seconds")
        save_post(post)
        updated += 1
    return updated
