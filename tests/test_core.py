import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from nara import core

CFG = {"timezone_offset_hours": 8, "timezone_label": "WITA", "max_posts_per_run": 1, "max_attempts": 3,
       "label_ai": "Visual dibuat dengan AI", "label_affiliate": "(link afiliasi)", "insights_days": 14}


class FakeThreads:
    def __init__(self, fail_reply=False, fail_post=False):
        self.calls = []
        self.fail_reply = fail_reply
        self.fail_post = fail_post

    def post(self, text, image_urls=(), reply_to_id=None):
        if reply_to_id and self.fail_reply:
            raise RuntimeError("reply gagal")
        if not reply_to_id and self.fail_post:
            raise RuntimeError("post gagal")
        self.calls.append((text, list(image_urls), reply_to_id))
        return f"id{len(self.calls)}"

    def permalink(self, mid):
        return f"https://threads.com/p/{mid}"

    def insights(self, mid):
        return {"views": 10}


class FakeGH:
    def __init__(self, body=None):
        self.issue = {"number": 1, "body": body} if body is not None else None
        self.comments = []

    def ensure_label(self):
        pass

    def find_queue_issue(self):
        return self.issue

    def create_issue(self, title, body):
        self.issue = {"number": 1, "body": body}
        return self.issue

    def update_issue_body(self, number, body):
        self.issue["body"] = body

    def comment(self, number, body):
        self.comments.append(body)


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "queue").mkdir()
        (self.root / "images").mkdir()

    def tearDown(self):
        shutil.rmtree(self.root)

    def add(self, pid, when="2026-11-06T10:00:00+08:00", **kw):
        data = {"id": pid, "status": "draft", "scheduled_at": when, "text": f"Halo {pid}", **kw}
        (self.root / "queue" / f"{pid}.json").write_text(json.dumps(data))

    def posts(self):
        return core.load_posts(self.root / "queue")

    def test_labels_added(self):
        p = {"text": "Outfit", "images": ["images/a.jpg"], "reply_text": "Kemeja: https://s.shopee.co.id/x"}
        text, reply = core.final_texts(p, CFG)
        self.assertIn("Visual dibuat dengan AI", text)
        self.assertIn("(link afiliasi)", reply)
        p2 = {"text": "Teks saja", "reply_text": "link afiliasi: https://s.shopee.co.id/x"}
        self.assertEqual(core.final_texts(p2, CFG), ("Teks saja", "link afiliasi: https://s.shopee.co.id/x"))

    def test_issue_keeps_checks_and_posting_flow(self):
        self.add("a")
        self.add("b", when="2026-11-06T20:00:00+08:00")
        self.add("c", images=["images/c.jpg"])
        gh = FakeGH()
        num, approved = core.sync_issue(gh, self.posts(), CFG, self.root)
        self.assertEqual(approved, set())
        self.assertIn("- [ ] `a`", gh.issue["body"])
        # pengguna mencentang a, b, c
        gh.issue["body"] = gh.issue["body"].replace("- [ ] `a`", "- [x] `a`") \
            .replace("- [ ] `b`", "- [x] `b`").replace("- [ ] `c`", "- [x] `c`")
        _, approved = core.sync_issue(gh, self.posts(), CFG, self.root)
        self.assertEqual(approved, {"a", "b", "c"})
        self.assertIn("- [x] `a`", gh.issue["body"])

        now = datetime(2026, 11, 6, 3, 0, tzinfo=timezone.utc)  # 11:00 WITA
        th = FakeThreads()
        posts = self.posts()
        done, errors = core.run_posting(th, posts, approved, CFG, now=now, root=self.root,
                                        url_for=lambda r: "u/" + r, log=lambda *a: None)
        self.assertEqual([p["id"] for p in done], ["a"])  # c menunggu gambar, b belum waktunya
        self.assertEqual(errors, [])
        saved = json.loads((self.root / "queue" / "a.json").read_text())
        self.assertEqual(saved["status"], "posted")
        # c: gambar diunggah, lalu terposting di run berikutnya
        (self.root / "images" / "c.jpg").write_bytes(b"x")
        done, _ = core.run_posting(th, self.posts(), approved, CFG, now=now, root=self.root,
                                   url_for=lambda r: "u/" + r, log=lambda *a: None)
        self.assertEqual([p["id"] for p in done], ["c"])
        self.assertEqual(th.calls[-1][1], ["u/images/c.jpg"])
        self.assertIn("Visual dibuat dengan AI", th.calls[-1][0])
        # setelah terposting, a dan c hilang dari issue
        core.sync_issue(gh, self.posts(), CFG, self.root)
        self.assertNotIn("`a`", gh.issue["body"])
        self.assertIn("- [x] `b`", gh.issue["body"])

    def test_unapproved_never_posted(self):
        self.add("a")
        th = FakeThreads()
        done, _ = core.run_posting(th, self.posts(), set(), CFG,
                                   now=datetime(2026, 11, 7, tzinfo=timezone.utc), root=self.root,
                                   url_for=str, log=lambda *a: None)
        self.assertEqual(done, [])
        self.assertEqual(th.calls, [])

    def test_reply_retry_and_failures(self):
        self.add("a", reply_text="https://s.shopee.co.id/x")
        now = datetime(2026, 11, 7, tzinfo=timezone.utc)
        th = FakeThreads(fail_reply=True)
        done, errors = core.run_posting(th, self.posts(), {"a"}, CFG, now=now, root=self.root,
                                        url_for=str, log=lambda *a: None)
        self.assertEqual(len(done), 1)
        self.assertEqual(len(errors), 1)
        th.fail_reply = False
        done, errors = core.run_posting(th, self.posts(), {"a"}, CFG, now=now, root=self.root,
                                        url_for=str, log=lambda *a: None)
        saved = json.loads((self.root / "queue" / "a.json").read_text())
        self.assertTrue(saved["reply_id"])
        self.assertEqual(th.calls[-1][2], saved["threads_id"])
        # posting gagal 3x -> failed
        self.add("b")
        th2 = FakeThreads(fail_post=True)
        for _ in range(3):
            core.run_posting(th2, self.posts(), {"b"}, CFG, now=now, root=self.root, url_for=str,
                             log=lambda *a: None)
        self.assertEqual(json.loads((self.root / "queue" / "b.json").read_text())["status"], "failed")

    def test_validate(self):
        self.add("x", text="a" * 501)
        probs = core.validate(self.posts()[0], CFG, self.root)
        self.assertTrue(any("501" in p for p in probs))

    def test_real_queue_valid(self):
        cfg = core.load_config()
        for post in core.load_posts():
            self.assertEqual(core.validate(post, cfg), [], post["_path"].name)


if __name__ == "__main__":
    unittest.main()


class WatermarkTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_jpeg_keeps_provenance_segments(self):
        import io
        import struct
        from PIL import Image
        from nara import watermark as wm
        buf = io.BytesIO()
        Image.new("RGB", (800, 1000), (200, 180, 160)).save(buf, "JPEG")
        raw = buf.getvalue()
        app11 = b"\xff\xeb" + struct.pack(">H", 2 + 10) + b"JPc2pa1234"
        raw = raw[:2] + app11 + raw[2:]
        out = wm.watermark_bytes(raw, "@nara.mixmatch")
        self.assertIn(b"JPc2pa1234", out)
        self.assertNotEqual(Image.open(io.BytesIO(out)).getpixel((760, 960)), (200, 180, 160))

    def test_png_keeps_chunks_and_manifest(self):
        import zlib
        import struct
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
        from nara import watermark as wm
        info = PngInfo()
        info.add_itxt("c2pa", "asal-gemini")
        p = self.dir / "a.png"
        Image.new("RGB", (600, 600), (10, 20, 30)).save(p, pnginfo=info)
        self.assertFalse(wm.is_watermarked(p))
        self.assertEqual(wm.process_dir(self.dir, "@nara.mixmatch", log=lambda *a: None), 1)
        self.assertTrue(wm.is_watermarked(p))
        self.assertIn(b"asal-gemini", p.read_bytes())
        self.assertEqual(Image.open(p).text.get("c2pa"), "asal-gemini")
        # tidak diproses dua kali
        self.assertEqual(wm.process_dir(self.dir, "@nara.mixmatch", log=lambda *a: None), 0)

    def test_post_waits_for_watermark(self):
        from PIL import Image
        root = self.dir
        (root / "images").mkdir()
        Image.new("RGB", (400, 400)).save(root / "images" / "x.jpg")
        post = {"images": ["images/x.jpg"]}
        cfg = dict(CFG, watermark_text="@nara.mixmatch")
        self.assertIn("menunggu watermark", " ".join(core.image_problems(post, root, cfg)))
        from nara import watermark as wm
        wm.process_dir(root / "images", "@nara.mixmatch", log=lambda *a: None)
        self.assertEqual(core.image_problems(post, root, cfg), [])
