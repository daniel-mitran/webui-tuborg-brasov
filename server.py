#!/usr/bin/env python3
"""
Single Malt · Radisson Blu Brasov (23 octombrie 2026) - check-in invitati,
sincronizat pe mai multe tablete. Fara PIN.

- Lista de invitati e STATICA: guests.json, generat o singura data din Excel
  cu import_excel.py (coloana A = nume, coloana B = numar de invitati).
- Bifarile se salveaza in checkins.json din $DATA_DIR (discul persistent pe
  Render), deci supravietuiesc restartului / redeploy-ului.
- Pentru o invitatie de mai multe persoane se poate nota cate au venit.

Productie: Render.com (vezi render.yaml), portul vine din $PORT.
Local:     python3 server.py   apoi   http://<IP-laptop>:8080
Doar biblioteca standard Python 3.8+, fara instalari.
"""

import argparse
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR") or HERE
os.makedirs(DATA_DIR, exist_ok=True)
CHECKINS_FILE = os.path.join(DATA_DIR, "checkins.json")
GUESTS_FILE = os.path.join(HERE, "guests.json")
INDEX_FILE = os.path.join(HERE, "index.html")
STATIC_DIR = os.path.join(HERE, "static")
STATIC_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml",
                ".ico": "image/x-icon", ".webp": "image/webp"}

LOCK = threading.Lock()


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


class Store:
    def __init__(self):
        db = load_json(GUESTS_FILE, None)
        if not db or not db.get("guests"):
            raise SystemExit("guests.json lipseste sau e gol - ruleaza import_excel.py")
        self.title = db.get("title", "")
        self.subtitle = db.get("subtitle", "")
        self.guests = db["guests"]
        self.by_id = {g["id"]: g for g in self.guests}
        saved = load_json(CHECKINS_FILE, {})
        # bifarile pentru id-uri care nu mai exista in lista sunt ignorate
        self.checkins = {k: v for k, v in saved.items() if k in self.by_id}
        self.version = 1

    def snapshot(self, with_guests=False):
        with LOCK:
            out = {"version": self.version, "checkins": self.checkins,
                   "serverTime": int(time.time() * 1000)}
            if with_guests:
                out.update(title=self.title, subtitle=self.subtitle, guests=self.guests)
            return out

    def _save(self):
        self.version += 1
        atomic_write_json(CHECKINS_FILE, self.checkins)

    def checkin(self, gid, n=None):
        g = self.by_id.get(gid)
        if not g:
            return False
        with LOCK:
            if gid in self.checkins:
                return False
            n = g["count"] if n is None else n
            self.checkins[gid] = {"ts": int(time.time() * 1000), "n": max(1, min(int(n), 99))}
            self._save()
            return True

    def set_count(self, gid, n):
        with LOCK:
            c = self.checkins.get(gid)
            if not c:
                return False
            c["n"] = max(1, min(int(n), 99))
            self._save()
            return True

    def undo(self, gid):
        with LOCK:
            if gid not in self.checkins:
                return False
            del self.checkins[gid]
            self._save()
            return True

    def reset(self):
        with LOCK:
            self.checkins = {}
            self._save()


STORE = None


class Handler(BaseHTTPRequestHandler):
    server_version = "SingleMaltCheckin/1.0"

    def log_message(self, fmt, *args):
        line = args[0] if args and isinstance(args[0], str) else ""
        if "/api/state" not in line and "/healthz" not in line and "/static/" not in line:
            print("[%s] %s" % (self.client_address[0], fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8", cache="no-store"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            with open(INDEX_FILE, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if u.path == "/healthz":
            return self._send(200, {"ok": True, "guests": len(STORE.guests)})
        if u.path.startswith("/static/"):
            name = os.path.basename(u.path)
            path = os.path.join(STATIC_DIR, name)
            ext = os.path.splitext(name)[1].lower()
            if ext in STATIC_TYPES and os.path.isfile(path):
                with open(path, "rb") as f:
                    return self._send(200, f.read(), STATIC_TYPES[ext], "public, max-age=3600")
            return self._send(404, {"error": "not found"})
        if u.path == "/api/state":
            return self._send(200, STORE.snapshot(with_guests="full=1" in (u.query or "")))
        self._send(404, {"error": "not found"})

    def do_HEAD(self):
        self.send_response(200 if urlparse(self.path).path in ("/", "/healthz") else 404)
        self.end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        b = self._body()
        gid = b.get("id")
        try:
            if u.path == "/api/checkin":
                ok = STORE.checkin(gid, b.get("n"))
            elif u.path == "/api/count":
                ok = STORE.set_count(gid, b.get("n"))
            elif u.path == "/api/undo":
                ok = STORE.undo(gid)
            elif u.path == "/api/reset":
                if b.get("confirm") != "RESET":
                    return self._send(400, {"error": "confirmare lipsa"})
                STORE.reset()
                ok = True
            else:
                return self._send(404, {"error": "not found"})
        except (TypeError, ValueError):
            return self._send(400, {"error": "date invalide"})
        self._send(200, {"ok": ok, **STORE.snapshot()})


def local_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def main():
    global STORE
    ap = argparse.ArgumentParser(description="Single Malt Brasov - check-in invitati")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    a = ap.parse_args()
    STORE = Store()
    print("  %d invitatii, %d persoane, %d deja bifate" % (
        len(STORE.guests), sum(g["count"] for g in STORE.guests), len(STORE.checkins)))
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    print("\n  Check-in pornit. Pe tablete deschide:")
    for ip in local_ips() or ["<IP-laptop>"]:
        print("    http://%s:%d" % (ip, a.port))
    print("  (Ctrl+C pentru oprire)\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nOprit.")


if __name__ == "__main__":
    main()
