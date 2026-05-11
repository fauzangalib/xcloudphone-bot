# XCloudPhone Bot

Automation script untuk [https://app.xcloudphone.com/](https://app.xcloudphone.com/) menggunakan Python Playwright.

## Fitur

- **Persistent Browser Profile** — Session login tersimpan, tidak perlu login ulang setiap kali menjalankan script
- **Non-Headless Browser** — Browser tampil secara visual sehingga bisa login manual pada run pertama
- **Screenshot Dashboard** — Otomatis mengambil screenshot dashboard dan menyimpannya dengan timestamp
- **Session Persistence** — Data cookies, localStorage, dan session disimpan di folder `browser_profile/`

## Persyaratan

- Python 3.8+
- Google Chrome / Chromium

## Instalasi

```bash
# Clone repository
git clone https://github.com/fauzangalib/xcloudphone-bot.git
cd xcloudphone-bot

# Install dependencies
pip install -r requirements.txt

# Install browser Chromium untuk Playwright
playwright install chromium
```

## Penggunaan

```bash
python run.py
```

### Alur Kerja

1. **Run Pertama** — Browser akan terbuka dan mengarah ke halaman login. Login secara manual.
2. **Run Berikutnya** — Script akan otomatis masuk ke dashboard karena session sudah tersimpan.
3. **Screenshot** — Setelah dashboard termuat, screenshot otomatis disimpan di folder `screenshots/`.

## Struktur Folder

```
xcloudphone-bot/
├── run.py              # Script utama
├── requirements.txt    # Dependencies
├── README.md           # Dokumentasi
├── browser_profile/    # Persistent browser data (auto-generated)
└── screenshots/        # Hasil screenshot (auto-generated)
```

## Catatan

- Folder `browser_profile/` berisi data session. **Jangan hapus** jika ingin mempertahankan login.
- Folder `browser_profile/` dan `screenshots/` sudah di-ignore oleh `.gitignore`.
- Jika session expired, cukup jalankan ulang script dan login manual kembali.

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Browser tidak muncul | Pastikan `headless=False` di `run.py` |
| Login tidak tersimpan | Pastikan folder `browser_profile/` tidak dihapus |
| Timeout saat loading | Periksa koneksi internet |
| Playwright error | Jalankan `playwright install chromium` |
