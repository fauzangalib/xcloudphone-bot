"""
XCloudPhone CLI
===============
CLI tipis di atas `xcp_api.XCloudPhoneClient` untuk operasi umum.

Contoh pemakaian:

    # list device aktif
    python xcp_cli.py sessions

    # stat ringkas
    python xcp_cli.py stats

    # reboot device tertentu (pakai short id atau session id)
    python xcp_cli.py reboot 309535
    python xcp_cli.py reboot 019e15c6-0354-71ce-acfd-effda9fc6fe5

    # info akun & saldo
    python xcp_cli.py me

    # notifikasi
    python xcp_cli.py notif

    # ambil kredensial TURN (untuk WebRTC)
    python xcp_cli.py turn 309535

    # raw request
    python xcp_cli.py raw GET /renters/packages

Cookie dibaca dari `.env`:

    XCP_COOKIE="renterAccessToken=...; renterRefreshToken=..."

atau

    XCP_ACCESS_TOKEN=...
    XCP_REFRESH_TOKEN=...
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from xcp_api import XCPError, XCloudPhoneClient


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _fmt_time(iso: Optional[str]) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    except ValueError:
        return iso


def _fmt_remaining(end_time: Optional[str]) -> str:
    if not end_time:
        return "-"
    end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    delta = end - datetime.now(tz=timezone.utc)
    if delta.total_seconds() <= 0:
        return "expired"
    mins = int(delta.total_seconds() // 60)
    h, m = divmod(mins, 60)
    return f"{h}h {m}m"


def _resolve_session(
    client: XCloudPhoneClient, ident: str
) -> Dict[str, Any]:
    """Resolve by UUID, shortId, or sessionName."""
    sessions = client.active_sessions()
    for s in sessions:
        if s["id"] == ident:
            return s
        dev = s.get("device") or {}
        if dev.get("shortId") == ident or dev.get("id") == ident:
            return s
        if s.get("sessionName") == ident:
            return s
    raise XCPError(f"Session tidak ditemukan: {ident}")


# ---------- commands --------------------------------------------------------


def cmd_check(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    from xcp_api import decode_jwt
    ap = decode_jwt(client.access_token)
    rp = decode_jwt(client.refresh_token)
    now = int(time.time())
    a_left = ap["exp"] - now
    r_left = rp["exp"] - now
    print(f"User       : {ap.get('username','?')}  (id {ap.get('sub','?')[:13]}...)")
    print(f"Role       : {ap.get('role','?')}")
    print(f"Access  exp: {_fmt_time(datetime.fromtimestamp(ap['exp'], tz=timezone.utc).isoformat())}"
          f"  ({'EXPIRED' if a_left <= 0 else f'{a_left}s left'})")
    print(f"Refresh exp: {_fmt_time(datetime.fromtimestamp(rp['exp'], tz=timezone.utc).isoformat())}"
          f"  ({'EXPIRED' if r_left <= 0 else f'{r_left // 3600}h left'})")
    if a_left <= 0 and r_left <= 0:
        print("\n[!] Kedua token expired. Ambil cookie baru dari browser.")
        return
    # Uji request ringan
    try:
        user = client.me()
        print(f"\n[ok] Auth works. Balance: {user.get('balance')} {user.get('walletCurrency')}")
    except Exception as e:
        print(f"\n[!] Auth failed: {e}")


def cmd_me(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    user = client.me()
    if args.json:
        _print_json(user)
        return
    print(f"User        : {user['username']} ({user['firstName']} {user['lastName']})")
    print(f"Email       : {user['email']}")
    print(f"ID          : {user['id']}")
    print(f"Country     : {user['country']}")
    print(f"Balance     : {user['balance']} {user['walletCurrency']}")
    print(f"Free hours  : {user.get('freeHoursBalance', 0)}")
    print(
        f"Storage     : {user['usedStorage'] / 1024 / 1024:.1f} MB / "
        f"{user['maxStorage'] / 1024 / 1024:.1f} MB"
    )
    print(f"2FA         : {'on' if user.get('isTwoFactorEnabled') else 'off'}")


def cmd_sessions(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    data = client.active_sessions()
    if args.json:
        _print_json(data)
        return
    if not data:
        print("(tidak ada session aktif)")
        return
    print(f"{'#':<2} {'shortId':<8} {'model':<22} {'online':<6} "
          f"{'remain':<9} {'package':<20} {'session id'}")
    print("-" * 110)
    for i, s in enumerate(data, 1):
        dev = s.get("device") or {}
        pkg = dev.get("packageCode") or "-"
        print(
            f"{i:<2} {dev.get('shortId','-'):<8} {dev.get('model','-')[:22]:<22} "
            f"{'yes' if dev.get('isOnline') else 'no':<6} "
            f"{_fmt_remaining(s.get('endTime')):<9} "
            f"{pkg[:20]:<20} {s['id']}"
        )


def cmd_stats(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    data = client.session_stats()
    if args.json:
        _print_json(data)
        return
    for row in data:
        print(f"  {row['stat']:<10}: {row['count']}")


def cmd_notif(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    unread = client.unread_count()
    data = client.notifications(page=1, limit=args.limit)
    if args.json:
        _print_json({"unread": unread, "notifications": data})
        return
    print(f"Unread: {unread.get('count', unread)}")
    items = data.get("data", data) if isinstance(data, dict) else data
    for n in items or []:
        ts = _fmt_time(n.get("createdAt"))
        print(f"  [{ts}] {n.get('title') or n.get('type') or '?'}")
        if n.get("message"):
            print(f"     {n['message']}")


def cmd_reboot(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    s = _resolve_session(client, args.target)
    print(f"[*] Reboot: {s['sessionName']} (shortId={s['device']['shortId']})")
    res = client.reboot(s["id"], command=args.command)
    _print_json(res)


def cmd_extend(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    s = _resolve_session(client, args.target)
    print(f"[*] Extend {args.hours}h: {s['sessionName']}")
    res = client.extend_rental(s["id"], hours=args.hours)
    _print_json(res)


def cmd_turn(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    s = _resolve_session(client, args.target)
    res = client.turn_credentials(
        device_id=s["deviceId"] if "deviceId" in s else s["device"]["id"],
        session_id=s["id"],
    )
    _print_json(res)


def cmd_balance(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    data = client.balance_transactions(limit=args.limit)
    if args.json:
        _print_json(data)
        return
    items = data.get("data", data) if isinstance(data, dict) else data
    for t in items or []:
        print(
            f"  [{_fmt_time(t.get('createdAt'))}] {t.get('type','-'):<14} "
            f"{t.get('amount','-'):>10} {t.get('status','-')} "
            f"{t.get('description','')}"
        )


def cmd_raw(client: XCloudPhoneClient, args: argparse.Namespace) -> None:
    body = json.loads(args.body) if args.body else None
    res = client.request(args.method.upper(), args.path, json_body=body)
    _print_json(res)


# ---------- entry -----------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="xcp", description="XCloudPhone CLI")
    p.add_argument("--json", action="store_true", help="output JSON")
    p.add_argument(
        "--env-file", default=".env", help="path .env (default: .env)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="cek validitas cookie & expiry token")
    sub.add_parser("me", help="info akun & saldo")
    sub.add_parser("sessions", help="list device yang lagi di-rent")
    sub.add_parser("stats", help="statistik sessions (online/offline/all)")

    pn = sub.add_parser("notif", help="notifikasi terbaru")
    pn.add_argument("--limit", type=int, default=10)

    pb = sub.add_parser("balance", help="riwayat transaksi saldo")
    pb.add_argument("--limit", type=int, default=20)

    pr = sub.add_parser("reboot", help="reboot device (shortId/session-id)")
    pr.add_argument("target")
    pr.add_argument("--command", default="reboot",
                    choices=["reboot", "soft-reboot"])

    pe = sub.add_parser("extend", help="perpanjang sewa")
    pe.add_argument("target")
    pe.add_argument("--hours", type=int, default=1)

    pt = sub.add_parser("turn", help="kredensial TURN untuk WebRTC")
    pt.add_argument("target")

    praw = sub.add_parser("raw", help="raw request ke API")
    praw.add_argument("method")
    praw.add_argument("path")
    praw.add_argument("--body", help="JSON body")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        client = XCloudPhoneClient.from_env(dotenv_path=args.env_file)
    except XCPError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2

    handlers = {
        "check": cmd_check,
        "me": cmd_me,
        "sessions": cmd_sessions,
        "stats": cmd_stats,
        "notif": cmd_notif,
        "balance": cmd_balance,
        "reboot": cmd_reboot,
        "extend": cmd_extend,
        "turn": cmd_turn,
        "raw": cmd_raw,
    }
    try:
        handlers[args.cmd](client, args)
    except XCPError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
