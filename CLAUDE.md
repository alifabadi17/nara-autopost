# Nara Autopost — instruksi untuk Claude

Repo ini menjalankan akun Threads afiliasi Shopee fashion wanita dengan karakter AI **Nara**
(model tanpa hijab, seri utama **#1Item3Acara**: satu item dipadukan untuk 3 acara).
GitHub Actions yang memposting; tugas Claude adalah mengisi antrean.

## Alur
1. Claude menulis draft ke `queue/<id>.json` lalu commit + push ke `main`.
2. Workflow `Posting Nara` memperbarui issue berlabel `antrean-nara`. Pemilik mencentang yang disetujui.
3. Draft yang dicentang, sudah waktunya, dan gambarnya lengkap diposting otomatis (maks 1 per 15 menit).
   Draft yang tidak dicentang TIDAK PERNAH diposting. Jangan pernah mengubah status jadi `posted` secara manual.

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
- Label "Visual dibuat dengan AI" otomatis ditambahkan ke teks bila ada gambar; hitung ruangnya (total ≤ 500).
- Jalankan `python3 -m nara validate` dan `python3 -m unittest discover -s tests` sebelum push.

## Gaya konten (dari riset)
- Kalimat pertama = hook: angka, situasi, atau masalah tubuh ("Buat yang petite…", "Rate 1–10…").
- Konteks spesifik: siapa (mahasiswa, karyawan, ibu muda) dan acara (kerja, kondangan, nongki).
- Bahasa obrolan, emoji 1–3, ajakan membalas di akhir. Link hanya di `reply_text`.
- Campur: ±50% postingan tanpa link (pertanyaan, opini ringan, polling) supaya akun tidak terlihat spam.
- Dilarang: klaim "bikin kurus/langsing", merendahkan bentuk tubuh atau daerah ("outfit kabupaten"),
  rage-bait, foto orang lain tanpa izin.

## Data performa
`queue/*.json` yang sudah terposting berisi `insights` (views, likes, replies, reposts, quotes, shares),
diperbarui tiap malam. Pakai ini untuk memilih hook dan jam yang berhasil.
