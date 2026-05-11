# XCloudPhone Bot

Automation toolkit untuk [app.xcloudphone.com](https://app.xcloudphone.com/).
Berisi dua pendekatan yang saling melengkapi:

| Pendekatan      | File        | Kegunaan                                                 |
|-----------------|-------------|----------------------------------------------------------|
| **REST API**    | `xcp_api.py`, `xcp_cli.py` | List/control session, reboot, extend, balance, dsb. Cepat & headless. |
| **Playwright**  | `run.py`    | Login interaktif (Google OAuth) + session persist. Buka halaman dashboard di browser. |

API dasar:
- REST backend: `https://api.xcloudphone.com` (NestJS, auth via cookie JWT)
- WebRTC gateway: `https://ws01.xcloudphone.com` (streaming + input, tidak di-cover oleh CLI ini)

## Instalasi

```bash
pip install -r requirements.txt
# optional - hanya kalau mau pakai run.py:
playwright install chromium
```

## Cara 1 — CLI berbasis cookie (disarankan)

### Ambil cookie
1. Login ke [app.xcloudphone.com](https://app.xcloudphone.com/) di browser.
2. DevTools (F12) → **Application** (Chrome) / **Storage** (Firefox) → Cookies → `app.xcloudphone.com`.
3. Copy nilai **`renterAccessToken`** dan **`renterRefreshToken`**.

### Konfigurasi
```bash
cp .env.example .env
# isi .env dengan cookie:
# XCP_COOKIE=renterAccessToken=eyJ...; renterRefreshToken=eyJ...
```

### Pemakaian
```bash
python xcp_cli.py check              # cek validitas cookie
python xcp_cli.py me                 # info akun & saldo
python xcp_cli.py sessions           # list device yg sedang di-rent
python xcp_cli.py stats              # ringkasan online/offline/all
python xcp_cli.py notif --limit 5    # notifikasi
python xcp_cli.py balance            # riwayat transaksi

python xcp_cli.py reboot 309535      # reboot device (shortId, uuid, atau sessionName)
python xcp_cli.py extend 309535 --hours 2

python xcp_cli.py turn 309535        # ambil kredensial TURN (WebRTC)
python xcp_cli.py raw GET /renters/packages
python xcp_cli.py --json sessions    # output JSON (untuk piping)
```

### Penting: Token Expiry
- **Access token** hanya berlaku **~15 menit** (auto di-refresh oleh client).
- **Refresh token** berlaku 7 hari, **tapi di-rotate**: setiap kali browser membuka
  app.xcloudphone.com, browser akan panggil refresh dan invalidate refresh token lama.
- **Artinya**: setelah copy cookie, jangan buka-tutup browser session lagi, atau
  cookie yang sudah kamu copy akan ikut ter-revoke.

Solusi praktis:
- **Logout dari browser** dulu, lalu login ulang, copy cookie, pakai CLI.
- Atau: buka DevTools → tab Network → filter `refresh` → copy cookie paling baru
  yang keluar dari response `Set-Cookie`.

## Cara 2 — Playwright (untuk akses UI)

Jalankan `run.py` kalau butuh:
- Login via Google OAuth
- Screenshot halaman dashboard
- Interaksi visual dengan UI

```bash
# Run pertama: login manual di browser yang terbuka
python run.py

# Run berikutnya: sudah auto-login karena profile tersimpan
python run.py

# Headless (hanya setelah sekali login):
HEADLESS=1 python run.py
```

## Endpoint API yang di-cover

Semua di bawah `https://api.xcloudphone.com`:

| Path                                                       | Method | Fungsi                                    |
|------------------------------------------------------------|--------|-------------------------------------------|
| `/auth/renters/me`                                         | GET    | info user                                 |
| `/auth/renters/refresh`                                    | POST   | rotate access+refresh token               |
| `/rentals/active`                                          | GET    | list session aktif (dengan socketToken)   |
| `/renters/rental-sessions`                                 | GET    | list sessions (paginated)                 |
| `/renters/rental-sessions/stats`                           | GET    | counter online/offline                    |
| `/renters/rental-sessions/{id}/user-reboot-action`         | POST   | reboot device                             |
| `/renters/rental-sessions/validate-sessions`               | POST   | validasi sesi                             |
| `/renters/adb-gateway/reboot-bulk`                         | POST   | reboot banyak sesi                        |
| `/rentals/extend`                                          | POST   | perpanjang sewa                           |
| `/rentals/rent`                                            | POST   | sewa device baru                          |
| `/renters/turn-xcloud?deviceId=&sessionId=`                | GET    | kredensial TURN untuk WebRTC              |
| `/renters/balance-transactions`                            | GET    | riwayat transaksi                         |
| `/renters/notifications/search`                            | GET    | notifikasi                                |
| `/renters/notifications/unread-count`                      | GET    | hitung unread                             |
| `/renters/user-devices`                                    | GET    | browser/device yang login                 |
| `/renters/session-groups`                                  | GET    | group sesi                                |
| `/renters/packages`                                        | GET    | paket yang tersedia                       |

## Batasan

CLI ini **tidak** mengakses stream video / kontrol touch device.
Untuk itu butuh WebRTC client (SDP offer/answer + DataChannel) ke
`ws01.xcloudphone.com` setelah mengambil TURN credentials via
`python xcp_cli.py turn <id>`. Implementasi WebRTC di luar scope CLI
ini—lebih mudah pakai Playwright ke halaman `/dashboard` yang sudah
di-handle oleh aplikasi webnya.

## Struktur

```
xcloudphone-bot/
├── xcp_api.py          # REST API client
├── xcp_cli.py          # CLI wrapper
├── run.py              # Playwright (login UI)
├── .env.example        # template config
├── .env                # (gitignored) cookie kamu
├── requirements.txt
├── browser_profile/    # (gitignored) profile Playwright
└── screenshots/        # (gitignored) hasil screenshot
```

## Keamanan

- File `.env` berisi token JWT yang **langsung bisa login sebagai akun kamu**. Jangan commit.
- Kalau tidak dipakai, **logout** di browser untuk invalidate semua token di server.
