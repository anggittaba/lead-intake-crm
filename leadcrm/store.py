"""Tiny SQLite CRM: leads, notifications, run log."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, run_id TEXT, source TEXT,
  name TEXT, email TEXT, phone TEXT, company TEXT, role TEXT, company_size TEXT, budget TEXT, timeline TEXT, message TEXT,
  raw TEXT, tier TEXT, points INTEGER, confidence REAL, reason TEXT, signals TEXT,
  llm_tier TEXT, llm_reason TEXT, status TEXT, review_reason TEXT, duplicate_of INTEGER, duplicate_reason TEXT,
  reviewed_tier TEXT, reviewed_note TEXT, expected_tier TEXT);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, run_id TEXT, lead_id INTEGER, channel TEXT, mode TEXT,
  status TEXT, attempts INTEGER, text TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS runlog (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, run_id TEXT, lead_id INTEGER, step TEXT, level TEXT, detail TEXT);
"""
LEAD_COLS = ("created_at run_id source name email phone company role company_size budget timeline message raw tier "
             "points confidence reason signals llm_tier llm_reason status review_reason duplicate_of duplicate_reason "
             "expected_tier").split()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript(SCHEMA)

    def reset(self):
        with self.lock:
            self.db.executescript("DELETE FROM leads; DELETE FROM notifications; DELETE FROM runlog;"
                                  "DELETE FROM sqlite_sequence;")

    def add_lead(self, rec: dict) -> int:
        rec = {**rec, "created_at": rec.get("created_at") or now()}
        for k in ("raw", "signals"):
            if not isinstance(rec.get(k), str):
                rec[k] = json.dumps(rec.get(k))
        with self.lock:
            cur = self.db.execute(f"INSERT INTO leads ({','.join(LEAD_COLS)}) VALUES ({','.join('?' * len(LEAD_COLS))})",
                                  [rec.get(c) for c in LEAD_COLS])
            self.db.commit()
            return cur.lastrowid

    def update_lead(self, lid: int, **kw):
        with self.lock:
            self.db.execute(f"UPDATE leads SET {','.join(k + '=?' for k in kw)} WHERE id=?", [*kw.values(), lid])
            self.db.commit()

    def lead(self, lid: int) -> dict | None:
        r = self.db.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
        return _lead(r) if r else None

    def leads(self, where: str = "1", args=()) -> list[dict]:
        return [_lead(r) for r in self.db.execute(f"SELECT * FROM leads WHERE {where} ORDER BY id", args)]

    def originals(self) -> list[dict]:
        return self.leads("duplicate_of IS NULL")

    def log(self, run_id: str, step: str, detail: str, lead_id: int | None = None, level: str = "info"):
        with self.lock:
            self.db.execute("INSERT INTO runlog (at,run_id,lead_id,step,level,detail) VALUES (?,?,?,?,?,?)",
                            (now(), run_id, lead_id, step, level, detail))
            self.db.commit()

    def runlog(self, limit: int = 500) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM runlog ORDER BY id DESC LIMIT ?", (limit,))]

    def add_notification(self, **kw) -> int:
        kw.setdefault("at", now())
        with self.lock:
            cur = self.db.execute(f"INSERT INTO notifications ({','.join(kw)}) VALUES ({','.join('?' * len(kw))})",
                                  list(kw.values()))
            self.db.commit()
            return cur.lastrowid

    def notifications(self, lead_id: int | None = None) -> list[dict]:
        q, a = ("SELECT * FROM notifications WHERE lead_id=? ORDER BY id", (lead_id,)) if lead_id else \
            ("SELECT * FROM notifications ORDER BY id DESC", ())
        return [dict(r) for r in self.db.execute(q, a)]


def _lead(r) -> dict:
    d = dict(r)
    for k in ("raw", "signals"):
        try:
            d[k] = json.loads(d[k]) if d[k] else None
        except (TypeError, ValueError):
            pass
    return d
