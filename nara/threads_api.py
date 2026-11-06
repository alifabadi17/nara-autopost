"""Klien kecil untuk Threads API resmi (graph.threads.net). Hanya pakai pustaka standar."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://graph.threads.net/v1.0"
ROOT = "https://graph.threads.net"


class ThreadsError(Exception):
    pass


def _request(method, url, params):
    params = {k: v for k, v in params.items() if v is not None}
    data = None
    if method == "GET":
        url = url + "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        # Jangan pernah mencetak URL (berisi token); cukup kode dan pesan server.
        raise ThreadsError(f"HTTP {e.code}: {body[:500]}") from None
    except urllib.error.URLError as e:
        raise ThreadsError(f"Koneksi gagal: {e.reason}") from None


class Threads:
    def __init__(self, token, poll_interval=3, poll_timeout=180):
        if not token:
            raise ThreadsError("THREADS_TOKEN kosong. Isi di Settings > Secrets > Actions.")
        self.token = token
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    def _get(self, path, **params):
        return _request("GET", f"{BASE}/{path}", {**params, "access_token": self.token})

    def _post(self, path, **params):
        return _request("POST", f"{BASE}/{path}", {**params, "access_token": self.token})

    def me(self):
        return self._get("me", fields="id,username")

    def create_container(self, **params):
        return self._post("me/threads", **params)["id"]

    def wait_ready(self, container_id):
        deadline = time.time() + self.poll_timeout
        while True:
            info = self._get(container_id, fields="status,error_message")
            status = info.get("status")
            if status in ("FINISHED", "PUBLISHED"):
                return
            if status in ("ERROR", "EXPIRED"):
                raise ThreadsError(f"Container {status}: {info.get('error_message')}")
            if time.time() > deadline:
                raise ThreadsError(f"Container belum siap setelah {self.poll_timeout} detik (status {status})")
            time.sleep(self.poll_interval)

    def publish(self, container_id):
        return self._post("me/threads_publish", creation_id=container_id)["id"]

    def post(self, text, image_urls=(), reply_to_id=None):
        """Buat dan terbitkan satu postingan. 0 gambar = teks, 1 = gambar, 2-10 = carousel."""
        image_urls = list(image_urls)
        if len(image_urls) > 10:
            raise ThreadsError("Maksimal 10 gambar per carousel")
        if not image_urls:
            cid = self.create_container(media_type="TEXT", text=text, reply_to_id=reply_to_id)
        elif len(image_urls) == 1:
            cid = self.create_container(media_type="IMAGE", image_url=image_urls[0], text=text,
                                        reply_to_id=reply_to_id)
        else:
            children = []
            for url in image_urls:
                child = self.create_container(media_type="IMAGE", image_url=url, is_carousel_item="true")
                self.wait_ready(child)
                children.append(child)
            cid = self.create_container(media_type="CAROUSEL", children=",".join(children), text=text,
                                        reply_to_id=reply_to_id)
        self.wait_ready(cid)
        return self.publish(cid)

    def permalink(self, media_id):
        return self._get(media_id, fields="permalink").get("permalink")

    def insights(self, media_id):
        data = self._get(f"{media_id}/insights", metric="views,likes,replies,reposts,quotes,shares")
        out = {}
        for item in data.get("data", []):
            values = item.get("values") or [{}]
            out[item["name"]] = item.get("total_value", {}).get("value", values[0].get("value"))
        return out

    def keyword_search(self, q, search_type="TOP", limit=25):
        fields = "id,text,permalink,timestamp,username,media_type"
        return self._get("keyword_search", q=q, search_type=search_type, fields=fields,
                         limit=limit).get("data", [])


def refresh_or_exchange(token, app_secret):
    """Perpanjang token jangka panjang; kalau gagal, tukar token jangka pendek jadi 60 hari.
    Mengembalikan (token_baru, expires_in_detik, cara)."""
    errors = []
    try:
        data = _request("GET", f"{ROOT}/refresh_access_token",
                        {"grant_type": "th_refresh_token", "access_token": token})
        return data["access_token"], data.get("expires_in"), "refresh"
    except ThreadsError as e:
        errors.append(f"refresh: {e}")
    if app_secret:
        try:
            data = _request("GET", f"{ROOT}/access_token",
                            {"grant_type": "th_exchange_token", "client_secret": app_secret,
                             "access_token": token})
            return data["access_token"], data.get("expires_in"), "exchange"
        except ThreadsError as e:
            errors.append(f"exchange: {e}")
    else:
        errors.append("exchange: THREADS_APP_SECRET kosong")
    raise ThreadsError("Gagal memperpanjang token. " + " | ".join(errors))
