"""
XCloudPhone REST API Client
============================
Client ringan untuk API backend `api.xcloudphone.com` yang dipakai oleh
aplikasi web `app.xcloudphone.com`.

Autentikasi memakai cookie `renterAccessToken` + `renterRefreshToken`
yang bisa di-copy dari DevTools browser (tab Application > Cookies).

Access token umurnya pendek (~15 menit). Client ini otomatis memanggil
`/auth/renters/refresh` saat mendapat HTTP 401, sehingga selama refresh
token masih valid (~7 hari), permintaan akan transparan.

Cara pakai:

    from xcp_api import XCloudPhoneClient

    client = XCloudPhoneClient.from_env()      # baca .env / env var
    print(client.me())
    for s in client.active_sessions():
        print(s["device"]["shortId"], s["sessionName"], s["device"]["isOnline"])

Token dibaca dari salah satu sumber (urut prioritas):
  1. argumen constructor
  2. file `.env` di folder kerja
  3. environment variable XCP_COOKIE  (string cookie lengkap)
  4. env var XCP_ACCESS_TOKEN + XCP_REFRESH_TOKEN
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

API_BASE = "https://api.xcloudphone.com"
APP_ORIGIN = "https://app.xcloudphone.com"
DEFAULT_TIMEOUT = 30


class XCPError(RuntimeError):
    """Error dari API atau client."""


# ---------- helpers ---------------------------------------------------------


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def decode_jwt(token: str) -> Dict[str, Any]:
    """Decode payload JWT tanpa verifikasi signature."""
    try:
        payload_b64 = token.split(".")[1]
        return json.loads(_b64url_decode(payload_b64))
    except Exception as exc:  # pragma: no cover
        raise XCPError(f"Token JWT tidak valid: {exc}") from exc


def parse_cookie_string(cookie_str: str) -> Dict[str, str]:
    """Parse header `Cookie: a=1; b=2` menjadi dict."""
    out: Dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out


def _load_dotenv(path: str = ".env") -> Dict[str, str]:
    """Parser .env sangat sederhana (tanpa dep `python-dotenv`)."""
    data: Dict[str, str] = {}
    if not os.path.isfile(path):
        return data
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.strip().strip('"').strip("'")
            data[k.strip()] = v
    return data


# ---------- client ----------------------------------------------------------


@dataclass
class XCloudPhoneClient:
    access_token: str
    refresh_token: str
    base_url: str = API_BASE
    origin: str = APP_ORIGIN
    session: requests.Session = field(default_factory=requests.Session)
    timeout: int = DEFAULT_TIMEOUT

    # ----- constructors -----------------------------------------------------

    @classmethod
    def from_cookie(cls, cookie_str: str, **kw) -> "XCloudPhoneClient":
        jar = parse_cookie_string(cookie_str)
        access = jar.get("renterAccessToken")
        refresh = jar.get("renterRefreshToken")
        if not access or not refresh:
            raise XCPError(
                "Cookie harus mengandung renterAccessToken & renterRefreshToken"
            )
        return cls(access_token=access, refresh_token=refresh, **kw)

    @classmethod
    def from_env(cls, dotenv_path: str = ".env", **kw) -> "XCloudPhoneClient":
        env = {**_load_dotenv(dotenv_path), **os.environ}
        cookie = env.get("XCP_COOKIE")
        if cookie:
            return cls.from_cookie(cookie, **kw)
        access = env.get("XCP_ACCESS_TOKEN")
        refresh = env.get("XCP_REFRESH_TOKEN")
        if not access or not refresh:
            raise XCPError(
                "Set XCP_COOKIE atau (XCP_ACCESS_TOKEN + XCP_REFRESH_TOKEN) di .env/env"
            )
        return cls(access_token=access, refresh_token=refresh, **kw)

    # ----- token handling ---------------------------------------------------

    @property
    def user_id(self) -> str:
        return decode_jwt(self.access_token).get("sub", "")

    @property
    def username(self) -> str:
        return decode_jwt(self.access_token).get("username", "")

    def access_token_exp(self) -> int:
        return int(decode_jwt(self.access_token).get("exp", 0))

    def _access_token_expired(self, skew: int = 30) -> bool:
        return time.time() + skew >= self.access_token_exp()

    def refresh_access_token(self) -> None:
        """Panggil /auth/renters/refresh untuk dapat access token baru."""
        url = f"{self.base_url}/auth/renters/refresh"
        cookies = {
            "renterAccessToken": self.access_token,
            "renterRefreshToken": self.refresh_token,
        }
        r = self.session.post(
            url,
            headers=self._base_headers(json=True),
            cookies=cookies,
            json={},
            timeout=self.timeout,
        )
        if r.status_code >= 400:
            raise XCPError(
                f"Gagal refresh token ({r.status_code}): {r.text[:300]}. "
                "Refresh token mungkin sudah kedaluwarsa/di-revoke. "
                "Ambil cookie baru dari browser."
            )
        # Server set cookie baru via Set-Cookie header
        new_access = r.cookies.get("renterAccessToken")
        new_refresh = r.cookies.get("renterRefreshToken")
        if new_access:
            self.access_token = new_access
        if new_refresh:
            self.refresh_token = new_refresh
        if not new_access:
            # fallback: kalau server tidak set cookie baru, mungkin token lama
            # masih bisa dipakai. Tapi biasanya Set-Cookie harus ada.
            raise XCPError("Refresh berhasil tapi tidak ada cookie baru di response")

    # ----- HTTP -------------------------------------------------------------

    def _base_headers(self, json: bool = False) -> Dict[str, str]:
        h = {
            "Origin": self.origin,
            "Referer": self.origin + "/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        }
        if json:
            h["Content-Type"] = "application/json"
        return h

    def _cookies(self) -> Dict[str, str]:
        return {
            "renterAccessToken": self.access_token,
            "renterRefreshToken": self.refresh_token,
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        auto_refresh: bool = True,
    ) -> Any:
        """Kirim request, auto-refresh kalau 401.

        Strategi: coba dulu dengan access token yang ada. Baru refresh kalau
        server benar-benar mengembalikan 401. Ini supaya refresh token yang
        masih valid tidak di-burn percuma untuk request yang tidak perlu auth
        yang fresh.
        """
        url = f"{self.base_url}{path}"

        def _do():
            return self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=self._base_headers(json=json_body is not None),
                cookies=self._cookies(),
                timeout=self.timeout,
            )

        r = _do()
        if r.status_code == 401 and auto_refresh:
            self.refresh_access_token()
            r = _do()

        if r.status_code >= 400:
            raise XCPError(
                f"{method} {path} -> HTTP {r.status_code}: {r.text[:400]}"
            )

        if not r.content:
            return None
        ctype = r.headers.get("content-type", "")
        if "application/json" in ctype:
            return r.json()
        return r.text

    # ----- account ----------------------------------------------------------

    def me(self) -> Dict[str, Any]:
        return self.request("GET", "/auth/renters/me")["user"]

    def balance_transactions(
        self, page: int = 1, limit: int = 20
    ) -> Dict[str, Any]:
        return self.request(
            "GET",
            "/renters/balance-transactions",
            params={"page": page, "limit": limit},
        )

    def notifications(self, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        return self.request(
            "GET",
            "/renters/notifications/search",
            params={"page": page, "limit": limit},
        )

    def unread_count(self) -> Dict[str, Any]:
        return self.request("GET", "/renters/notifications/unread-count")

    # ----- rental / sessions ------------------------------------------------

    def active_sessions(self) -> List[Dict[str, Any]]:
        """GET /rentals/active - list lengkap (dengan socketToken)."""
        return self.request("GET", "/rentals/active")

    def rental_sessions(
        self, page: int = 1, limit: int = 50, **filters
    ) -> Dict[str, Any]:
        """GET /renters/rental-sessions - view paginated."""
        params = {"page": page, "limit": limit, **filters}
        return self.request("GET", "/renters/rental-sessions", params=params)

    def session_stats(self) -> List[Dict[str, Any]]:
        return self.request("GET", "/renters/rental-sessions/stats")

    def validate_sessions(self, session_ids: List[str]) -> Any:
        return self.request(
            "POST",
            "/renters/rental-sessions/validate-sessions",
            json_body={"sessionIds": session_ids},
        )

    def reboot(self, session_id: str, command: str = "reboot") -> Any:
        """POST user-reboot-action. `command` biasanya 'reboot' atau 'soft-reboot'."""
        return self.request(
            "POST",
            f"/renters/rental-sessions/{session_id}/user-reboot-action",
            json_body={"command": command},
        )

    def reboot_bulk(self, session_ids: List[str], command: str = "reboot") -> Any:
        return self.request(
            "POST",
            "/renters/adb-gateway/reboot-bulk",
            json_body={"sessionIds": session_ids, "command": command},
        )

    def extend_rental(self, session_id: str, hours: int = 1) -> Any:
        return self.request(
            "POST",
            "/rentals/extend",
            json_body={"sessionId": session_id, "hours": hours},
        )

    def rent(self, payload: Dict[str, Any]) -> Any:
        """POST /rentals/rent. Payload tergantung paket; lihat dashboard."""
        return self.request("POST", "/rentals/rent", json_body=payload)

    def update_session(self, session_id: str, **fields) -> Any:
        return self.request(
            "PATCH",
            f"/renters/rental-sessions/{session_id}",
            json_body=fields,
        )

    # ----- streaming --------------------------------------------------------

    def turn_credentials(self, device_id: str, session_id: str) -> Dict[str, Any]:
        """
        GET /renters/turn-xcloud?deviceId=...&sessionId=...
        Mengembalikan iceServers untuk WebRTC ke ws01.xcloudphone.com.
        Response expired setelah ~15 menit.
        """
        return self.request(
            "GET",
            "/renters/turn-xcloud",
            params={"deviceId": device_id, "sessionId": session_id},
        )

    # ----- misc -------------------------------------------------------------

    def user_devices(self) -> Dict[str, Any]:
        """Device (browser) yang login ke akun - bukan cloud phone."""
        return self.request("GET", "/renters/user-devices")

    def packages(self) -> Any:
        return self.request("GET", "/renters/packages")

    def session_groups(self) -> Any:
        return self.request("GET", "/renters/session-groups")
