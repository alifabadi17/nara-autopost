# nara-autopost

Sistem posting otomatis akun Threads Nara (afiliasi Shopee fashion).

## Cara kerja harian
1. Draft postingan masuk ke folder `queue/` (dibuat Claude).
2. Semua draft **otomatis terposting** pada jadwalnya (tampil minimal 2 jam dulu di tab **Issues**).
3. Kalau ada yang tidak mau diposting: buka issue antrean, **centang untuk membatalkan**. Bisa dari HP lewat aplikasi GitHub.
4. **Bank gambar mingguan:** sekali seminggu buat 15–20 foto Nara di Gem (outfit dan acara berbeda),
   lalu unggah semuanya ke folder `images/bank/`. Claude memilih dan menulis caption dari foto-foto itu.
   Foto referensi wajah Nara (3–5 terbaik) cukup sekali diunggah ke `images/ref/`.
5. Kalau postingan butuh gambar yang belum ada dan pembuat otomatis tidak bisa: salin prompt-nya ke Gem *Nara Photo Studio*, buat gambarnya, lalu
   unggah ke folder `images/` (**Add file → Upload files**) dengan nama file persis seperti di daftar.
6. Selesai. Sistem memposting sendiri pada jadwalnya, lalu menulis link postingannya sebagai komentar di issue.

Hapus centang kalau batal membatalkan. Mode bisa diganti di `config.json` (`approval_mode`: manual / veto / auto).

## Secrets yang dibutuhkan (Settings → Secrets and variables → Actions)
| Nama | Isi |
| --- | --- |
| `THREADS_TOKEN` | Token dari Generator Token Pengguna di dashboard Meta |
| `THREADS_APP_SECRET` | Rahasia aplikasi Threads |
| `GEMINI_API_KEY` | API key dari aistudio.google.com (boleh free tier) |
| `GH_PAT` | Fine-grained token GitHub, hanya repo ini, izin **Secrets: Read and write** |

## Workflow
- **Posting Nara**: tiap ±15 menit, saat issue dicentang, dan saat antrean berubah.
- **Perpanjang token Threads**: tiap Senin, atau jalankan manual setelah membuat token baru.
- **Ambil insight Threads**: tiap malam, menyimpan views/likes/balasan ke file antrean.
