# Nara Autopost — instruksi untuk Claude

Repo ini menjalankan akun Threads afiliasi Shopee fashion wanita dengan karakter AI **Nara**
(model tanpa hijab, seri utama **#1Item3Acara**: satu item dipadukan untuk 3 acara).
GitHub Actions yang memposting; tugas Claude adalah mengisi antrean.

## Alur
1. Claude menulis draft ke `queue/<id>.json` lalu commit + push ke `main`.
2. Workflow `Posting Nara` memperbarui issue berlabel `antrean-nara`.
3. Mode persetujuan di `config.json` (`approval_mode`), saat ini **veto**: semua draft otomatis terposting
   pada jadwalnya, KECUALI pemilik mencentangnya (= batal). Draft harus tampil minimal `veto_window_hours`
   (2 jam) di issue sebelum boleh terposting, jadi push draft jauh sebelum jadwalnya (idealnya malam sebelumnya).
   Maks 1 postingan per 15 menit; postingan bergambar menunggu sampai gambarnya ada.
   Jangan pernah mengubah status jadi `posted` secara manual. Karena tanpa review wajib, cek ulang
   fakta (harga, rating, terjual) dan aturan gaya dengan teliti sebelum push.

## Format draft (`queue/<id>.json`)
```json
{
  "id": "2026-11-08-kemeja-putih",
  "status": "draft",
  "scheduled_at": "2026-11-08T12:30:00+08:00",
  "series": "1item3acara",
  "text": "Postingan utama, maks 500 karakter. Hook di kalimat pertama, TANPA link.",
  "reply_text": "Balasan berisi link Shopee per item. Label (link afiliasi) ditambah otomatis.",
  "images": ["images/2026-11-08-kemeja-putih-1.jpg"],
  "image_prompt": "Prompt lengkap untuk Gem Nara Photo Studio",
  "products": [{"item": "Kemeja putih oversized", "shop": "...", "url": "https://s.shopee.co.id/...", "price": 89000}]
}
```
- Nama file = `id` + `.json`. Zona waktu WITA (+08:00). Slot default ada di `config.json`.
- 0 gambar = postingan teks, 1 = gambar, 2–10 = carousel. Gambar JPG/PNG ≤ 8 MB di `images/`.
- Link TIDAK pernah ikut saat postingan utama terbit. `reply_text` diposting otomatis sebagai balasan
  minimal 60 menit kemudian dan hanya bila views ≥ 300; kalau dalam 24 jam tidak tembus, link batal
  (atur di `config.json`: `reply_delay_minutes`, `reply_min_views`, `reply_max_wait_hours`).
- Tidak ada label AI di caption (keputusan pemilik); transparansi lewat bio akun. Label "(link afiliasi)"
  tetap otomatis di balasan berlink.
- Sumber gambar, urutan prioritas:
  1. **Bank gambar** `images/bank/`: foto Nara yang dibuat pemilik di Gem secara batch. Lihat gambarnya,
     pilih yang belum pernah dipakai (cek `images` di semua file `queue/`), tulis caption yang sesuai
     outfit di gambar itu, lalu cari produk Shopee yang mirip. Pakai path `images/bank/<nama>`.
  2. **Gemini API otomatis**: isi `image_prompt` dan path baru `images/<id>-1.jpg` yang belum ada.
     Workflow membuatnya (gaya dari `prompts/nara.md` + referensi `images/ref/`), maks `gen_max_per_day`.
     STATUS 10 Nov 2026: free tier Gemini untuk model gambar berkuota 0, jadi `gen_max_per_day` = 0 (mati)
     sampai billing aktif. Untuk sekarang pakai bank gambar.
  3. Kalau keduanya tidak tersedia, pemilik membuat manual dari `image_prompt`.
  Jangan pernah mengubah atau memberi watermark pada `images/ref/`.
- Gambar di `images/` dan `images/bank/` otomatis diberi watermark `@nara.mixmatch` oleh workflow sebelum diposting.
  Metadata asli file (termasuk tanda asal AI) dipertahankan; jangan pernah menghapusnya.
- Jalankan `python3 -m nara validate` dan `python3 -m unittest discover -s tests` sebelum push.

## KONSEP AKTIF (13 Nov 2026): papan outfit dari foto produk, TANPA model
Pemilik ingin 100% otomatis. Gambar = papan mix & match 1080x1350 yang dibuat workflow dari foto produk
(`nara/board.py`). Untuk postingan bergambar, isi `boards` (bukan `image_prompt`):
```json
"boards": [{"title": "Ngantor", "subtitle": "Rapi tapi ga kaku",
            "items": [{"name": "MILLION Millionaire Pants", "price": 256500, "image": "products/x.jpg"}, ...]}]
```
Item pertama = item utama (diberi label "ITEM UTAMA"), maks 4 item per papan, 1 papan per acara.
Foto produk: tambahkan `"nama-file": "<url gambar susercontent>"` ke `products/urls.json`, push, lalu workflow
`Ambil foto produk` mengunduhnya ke `products/<nama-file>.jpg` (tunggu file ada sebelum menulis draft).
SETIAP item yang tampil di papan wajib punya link afiliasi di `reply_text` (permintaan pemilik).
Pakai ulang item "lemari kapsul" yang sudah punya foto + link bila cocok. Set `"ai_image": false`.
Konsep model AI Nara (bank gambar / Gemini) DITUNDA.

## Identitas akun
@nara.mixmatch, nama "Nara | 1 Item 3 Acara". Nara adalah karakter AI (disebut di bio).
Nara boleh berpendapat, bertanya, mengkurasi, dan memberi ide padu padan. Nara TIDAK mengaku membeli,
memakai, atau mencoba produk ("aku udah pake, bahannya adem"). Info kualitas diambil dari data Shopee
yang nyata dan disebut sumbernya: "rating 4.9, 10rb terjual, kata pembeli bahannya adem".

## Gaya konten (riset beranda Threads, 7 Nov 2026)
Postingan jualan terang-terangan sepi (0–30 suka): link + tagar, "Yuk checkout sekarang!",
pujian generik produk. Yang ramai adalah yang mengajak ngobrol warga Threads:
1. Ajakan pamer/spill ("PAMERIN … KALIAN + HARGANYA") → ratusan balasan.
2. Pertanyaan ringan yang semua orang bisa jawab ("spill meja kerja kalian").
3. Opini relate tanpa produk ("In this economy, baju preloved lebih menarik…").
4. Kurasi daftar 5–8 toko ("toko Shopee yang bahaya buat saldo") → banyak repost/simpan.
5. Info diskon besar dan nyata → banyak share.
6. Format kontras singkat (❌ / ❌ / ✅).
7. Humor jujur dan menyapa "warga Threads".
Aturan tulis: hook di kalimat pertama, boleh HURUF BESAR untuk emosi, bahasa obrolan, emoji 1–3,
konteks spesifik (siapa + acara + kisaran harga). Link hanya di `reply_text`.
Campur: ±50% postingan tanpa link. Dilarang: klaim "bikin kurus/langsing", merendahkan bentuk tubuh
atau daerah ("outfit kabupaten"), rage-bait, foto orang lain tanpa izin, testimoni palsu.

## Riset referensi
File di `research/` (mis. `research/helwa-bashel.md`) berisi toko dan gaya acuan pilihan pemilik.
Pakai sebagai sumber utama saat memilih produk. Jangan pakai link afiliasi atau foto milik kreator lain.

## Data performa
`queue/*.json` yang sudah terposting berisi `insights` (views, likes, replies, reposts, quotes, shares),
diperbarui tiap malam. Pakai ini untuk memilih hook dan jam yang berhasil.
