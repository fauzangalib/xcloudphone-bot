"""
XCloudPhone Bot - Playwright Automation
========================================
Automation script untuk https://app.xcloudphone.com/
Menggunakan persistent browser profile untuk mempertahankan session login.

LOGIN: Menggunakan Google OAuth (login manual pada run pertama)
- Run pertama: Browser terbuka → klik "Login with Google" → login manual
- Run berikutnya: Otomatis masuk (session tersimpan di browser_profile/)
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

# Timeout untuk menunggu login manual (5 menit)
LOGIN_TIMEOUT = 300000


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


def is_logged_in(page):
    """Cek apakah user sudah login berdasarkan URL dan konten halaman."""
    current_url = page.url.lower()

    # Jika URL mengandung kata-kata ini, berarti belum login
    login_indicators = ["login", "signin", "sign-in", "auth", "oauth"]
    for indicator in login_indicators:
        if indicator in current_url:
            return False

    # Jika URL mengandung kata-kata ini, berarti sudah login
    dashboard_indicators = ["dashboard", "app", "home", "panel"]
    for indicator in dashboard_indicators:
        if indicator in current_url:
            return True

    # Default: cek apakah ada elemen yang menandakan sudah login
    # (misalnya avatar user, menu, dll)
    try:
        # Tunggu sebentar untuk halaman loading
        page.wait_for_timeout(3000)
        # Cek apakah masih ada tombol login/sign in di halaman
        login_button = page.locator("text=/sign.?in|log.?in|login with google/i")
        if login_button.count() > 0:
            return False
    except Exception:
        pass

    return True


def wait_for_login(page):
    """Tunggu user login manual via Google."""
    print("")
    print("=" * 60)
    print("  LOGIN DIPERLUKAN - Silakan login di browser yang terbuka")
    print("=" * 60)
    print("")
    print("  Langkah-langkah:")
    print("  1. Klik tombol 'Login with Google' di browser")
    print("  2. Pilih akun Google kamu")
    print("  3. Selesaikan proses login")
    print("  4. Script akan otomatis melanjutkan setelah login berhasil")
    print("")
    print(f"  ⏳ Menunggu login... (timeout: {LOGIN_TIMEOUT // 1000} detik)")
    print("=" * 60)
    print("")

    # Tunggu sampai URL berubah (tidak lagi di halaman login)
    # Kita tunggu sampai URL tidak mengandung kata login/auth
    try:
        page.wait_for_function(
            """() => {
                const url = window.location.href.toLowerCase();
                const loginWords = ['login', 'signin', 'sign-in', 'auth', 'oauth', 'accounts.google'];
                return !loginWords.some(word => url.includes(word));
            }""",
            timeout=LOGIN_TIMEOUT,
        )
        print("[+] Login berhasil terdeteksi!")
        return True
    except Exception as e:
        print(f"[!] Timeout menunggu login: {e}")
        print("[!] Silakan jalankan ulang script dan coba login lagi.")
        return False


def run_automation():
    """Jalankan automation utama."""
    ensure_directories()

    print("[*] Memulai XCloudPhone Bot...")
    print(f"[*] Profile browser: {PROFILE_DIR}")
    print(f"[*] Target URL: {URL}")
    print(f"[*] Mode: {'headless' if HEADLESS else 'non-headless (visible)'}")
    print("")

    if HEADLESS:
        print("[!] PERHATIAN: Mode headless aktif.")
        print("[!] Jika belum pernah login, jalankan dulu TANPA HEADLESS=1")
        print("[!] agar bisa login manual via Google.")
        print("")

    with sync_playwright() as p:
        # Gunakan persistent context untuk mempertahankan session login
        # Browser non-headless agar user bisa login manual via Google
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

        # Tunggu halaman selesai loading
        page.wait_for_timeout(3000)

        # Cek apakah sudah login
        current_url = page.url
        print(f"[*] Halaman saat ini: {current_url}")

        if not is_logged_in(page):
            if HEADLESS:
                print("\n[ERROR] Belum login dan mode headless aktif!")
                print("[ERROR] Jalankan dulu tanpa HEADLESS=1 untuk login via Google:")
                print("[ERROR]   python run.py")
                print("[ERROR] Setelah login berhasil, baru jalankan dengan HEADLESS=1")
                context.close()
                sys.exit(1)

            # Mode non-headless: tunggu user login manual
            login_success = wait_for_login(page)
            if not login_success:
                context.close()
                sys.exit(1)

            # Tunggu halaman dashboard termuat sepenuhnya setelah login
            page.wait_for_timeout(5000)

        # Tunggu halaman dashboard termuat
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        print("[+] Dashboard berhasil dimuat.")

        # Ambil screenshot dashboard
        take_screenshot(page, "dashboard")

        # Tampilkan info halaman
        title = page.title()
        print(f"[*] Judul halaman: {title}")
        print(f"[*] URL: {page.url}")

        print("\n[+] Automation selesai!")
        print("[*] Session login tersimpan di browser_profile/")
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
