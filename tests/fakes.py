"""Shared fakes for the worker tests: an in-memory Base44 and a scripted robot."""

import itertools

import base44_client


class FakeBase44:
    """In-memory stand-in for base44_client: exact-match queries, compare-and-set claim.

    Every status write is logged, so tests can check a turn walked its statuses in order."""

    Base44Error = base44_client.Base44Error
    RateLimited = base44_client.RateLimited

    def __init__(self):
        self.records = {}
        self.status_log = []
        self._ids = itertools.count(1)

    def add(self, entity, **fields):
        rec = {"id": f"{entity}-{next(self._ids)}", **fields}
        self.records.setdefault(entity, []).append(rec)
        return rec

    def list_records(self, entity, query=None, sort=None, limit=100):
        rows = [r for r in self.records.get(entity, [])
                if all(r.get(k) == v for k, v in (query or {}).items())]
        if sort:
            rows.sort(key=lambda r: r.get(sort))
        return [dict(r) for r in rows[:limit]]

    def get(self, entity, record_id):
        return next(r for r in self.records[entity] if r["id"] == record_id)

    def get_record(self, entity, record_id):  # real client's name
        return dict(self.get(entity, record_id))

    def create_record(self, entity, fields):
        return dict(self.add(entity, **fields))

    def update_record(self, entity, record_id, fields):
        self.get(entity, record_id).update(fields)
        if "status" in fields:
            self.status_log.append((record_id, fields["status"]))
        return dict(self.get(entity, record_id))

    def claim(self, entity, record_id, from_status, fields):
        rec = self.get(entity, record_id)
        if rec.get("status") != from_status:
            return False
        rec.update(fields)
        if "status" in fields:
            self.status_log.append((record_id, fields["status"]))
        return True

    def statuses(self, record_id):
        return [status for rid, status in self.status_log if rid == record_id]


def heard(text):
    return {"status": "ok", "text": text}


class FakeRobot:
    """Scripted stand-in for furhat_client. `heard` is the queue of listen() results;
    an empty queue means silence."""

    def __init__(self, heard=(), connected=True):
        self.heard = list(heard)
        self.connected = connected
        self.calls = []
        self.backchannels = []  # the backchannel flag of each listen() call

    def _sent(self):
        return {"sent": self.connected, "reason": None if self.connected else "connection refused"}

    def say(self, text, language=None, gender=None):
        self.calls.append(("say", text))
        return self._sent()

    def react(self, emotion, intensity, text=None, language=None, gender=None):
        self.calls.append(("react", emotion, intensity, text))
        return self._sent()

    def listen(self, backchannel=True):
        self.calls.append(("listen",))
        self.backchannels.append(backchannel)
        if not self.connected:
            return {"status": "failed", "text": ""}
        return self.heard.pop(0) if self.heard else {"status": "no_speech", "text": ""}

    def health_check(self):
        return self.connected

    def said(self):
        return [c[1] for c in self.calls if c[0] == "say"]
