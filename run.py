"""
XCloudPhone Bot - Playwright Automation
========================================
Automation script untuk https://app.xcloudphone.com/
Menggunakan persistent browser profile untuk mempertahankan session login.
"""

import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright

# Konfigurasi
URL = "https://app.xcloudphone.com/"
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
# Set HEADLESS=1 untuk menjalankan tanpa GUI (server/CI), default: non-headless
HEADLESS = os.environ.get("HEADLESS", "0") == "1"


def ensure_directories():
    """Pastikan direktori yang diperlukan ada."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def take_screenshot(page, name="dashboard"):
    """Ambil screenshot dan simpan dengan timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    page.screenshot(path=filepath, full_page=True)
    print(f"[+] Screenshot disimpan: {filepath}")
    return filepath


def run_automation():
    """Jalankan automation utama."""
    ensure_directories()

    print("[*] Memulai XCloudPhone Bot...")
    print(f"[*] Profile browser: {PROFILE_DIR}")
    print(f"[*] Target URL: {URL}")
    print(f"[*] Mode: {'headless' if HEADLESS else 'non-headless (visible)'}")

    with sync_playwright() as p:
        # Gunakan persistent context untuk mempertahankan session login
        # HEADLESS=1 untuk server/CI, default non-headless agar user bisa login manual
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=HEADLESS,
            viewport={"width": 1280, "height": 720},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
            ],
        )

        # Gunakan halaman pertama atau buat baru
        if context.pages:
            page = context.pages[0]
        else:
            page = context.new_page()

        # Navigasi ke XCloudPhone
        print("[*] Membuka XCloudPhone...")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        # Cek apakah sudah login atau masih di halaman login
        current_url = page.url
        print(f"[*] Halaman saat ini: {current_url}")

        if "login" in current_url.lower() or "auth" in current_url.lower():
            print("[!] Belum login. Silakan login secara manual di browser yang terbuka.")
            print("[!] Setelah login, script akan otomatis melanjutkan...")
            # Tunggu sampai user login (URL berubah dari halaman login)
            page.wait_for_url("**/dashboard**", timeout=300000)  # Tunggu 5 menit
            print("[+] Login berhasil terdeteksi!")

        # Tunggu halaman dashboard termuat
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        print("[+] Dashboard berhasil dimuat.")

        # Ambil screenshot dashboard
        take_screenshot(page, "dashboard")

        # Tampilkan info halaman
        title = page.title()
        print(f"[*] Judul halaman: {title}")

        print("\n[+] Automation selesai!")
        print("[*] Session tersimpan di browser_profile/")
        print("[*] Pada eksekusi berikutnya, login tidak diperlukan lagi.")

        # Tutup browser
        context.close()


if __name__ == "__main__":
    try:
        run_automation()
    except KeyboardInterrupt:
        print("\n[!] Dihentikan oleh user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
