"""Perintah: python -m nara [validate|sync|post|watermark|insights|refresh-token|whoami]"""
import os
import sys

from . import core
from .threads_api import Threads, ThreadsError, refresh_or_exchange


def _threads():
    return Threads(os.environ.get("THREADS_TOKEN", "").strip())


def cmd_validate():
    cfg = core.load_config()
    bad = 0
    for post in core.load_posts():
        probs = core.validate(post, cfg)
        if probs:
            bad += 1
            print(f"{post['_path'].name}: " + "; ".join(probs))
    print("Semua antrean valid." if not bad else f"{bad} file bermasalah.")
    return 1 if bad else 0


def cmd_sync():
    from .github_api import GitHub
    cfg = core.load_config()
    number, approved = core.sync_issue(GitHub(), core.load_posts(), cfg)
    print(f"Issue #{number} diperbarui, {len(approved)} disetujui.")
    return 0


def cmd_post():
    from .github_api import GitHub
    cfg = core.load_config()
    gh = GitHub()
    posts = core.load_posts()
    number, approved = core.sync_issue(gh, posts, cfg)
    if not os.environ.get("THREADS_TOKEN", "").strip():
        print("THREADS_TOKEN belum diisi: antrean disinkronkan, posting dilewati.")
        return 0
    done, errors = core.run_posting(_threads(), posts, approved, cfg)
    if done or errors:
        core.sync_issue(gh, core.load_posts(), cfg)
        msg = []
        for p in done:
            msg.append(f"Terposting `{p['id']}`: {p.get('permalink') or p['threads_id']}")
        for e in errors:
            msg.append(f"Gagal: {e}")
        gh.comment(number, "\n".join(msg))
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    return 1 if errors else 0


def cmd_insights():
    cfg = core.load_config()
    n = core.run_insights(_threads(), core.load_posts(), cfg)
    print(f"Insight diperbarui untuk {n} postingan.")
    return 0


def cmd_refresh_token(out_path):
    token = os.environ.get("THREADS_TOKEN", "").strip()
    secret = os.environ.get("THREADS_APP_SECRET", "").strip()
    new_token, expires_in, how = refresh_or_exchange(token, secret)
    me = Threads(new_token).me()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(new_token)
    days = round((expires_in or 0) / 86400)
    print(f"Token diperbarui lewat {how} untuk @{me.get('username')}; berlaku ±{days} hari.")
    return 0


def cmd_watermark():
    from .watermark import process_dir
    cfg = core.load_config()
    text = cfg.get("watermark_text")
    if not text:
        print("watermark_text kosong di config.json, dilewati.")
        return 0
    n = process_dir(core.REPO_ROOT / "images", text)
    print(f"{n} gambar diberi watermark.")
    return 0


def cmd_whoami():
    me = _threads().me()
    print(f"Token valid untuk @{me.get('username')} (id {me.get('id')}).")
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    try:
        if cmd == "validate":
            return cmd_validate()
        if cmd == "sync":
            return cmd_sync()
        if cmd == "post":
            return cmd_post()
        if cmd == "insights":
            return cmd_insights()
        if cmd == "refresh-token":
            return cmd_refresh_token(argv[1] if len(argv) > 1 else "new_token.txt")
        if cmd == "watermark":
            return cmd_watermark()
        if cmd == "whoami":
            return cmd_whoami()
    except ThreadsError as e:
        print(f"ERROR Threads: {e}", file=sys.stderr)
        return 1
    print(f"Perintah tidak dikenal: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
