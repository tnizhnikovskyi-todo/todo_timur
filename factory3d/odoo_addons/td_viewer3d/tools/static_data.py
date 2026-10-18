"""Кеш статичних файлів переглядача в пам'яті воркера (API-01, API-07)."""
import gzip
import hashlib
import json
import os
import threading

_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
STATIC_PATH = os.path.join(_BASE, "data", "model_static.json")
MANIFEST_PATH = os.path.join(_BASE, "model", "parts", "manifest.json")
PARTS_URL = "/factory3d_viewer/static/model/parts/%s.glb?v=%s"

_lock = threading.Lock()
_cache = {}


def _stamp(path):
    st = os.stat(path)
    return (st.st_mtime_ns, st.st_size)


def _entry(path, builder):
    stamp = _stamp(path)
    with _lock:
        hit = _cache.get(path)
        if hit and hit["stamp"] == stamp:
            return hit
    with open(path, "rb") as fh:
        raw = fh.read()
    entry = {"stamp": stamp, "sha1": hashlib.sha1(raw).hexdigest()}
    entry.update(builder(raw))
    with _lock:
        _cache[path] = entry
    return entry


def _static_builder(raw):
    data = json.loads(raw)
    sha1 = hashlib.sha1(raw).hexdigest()
    out = dict(data)
    src = data.get("meta") or {}
    out["meta"] = {"schema": src.get("schema", "1.1"), "built_at": src.get("built_at"),
                   "static_etag": sha1[:16]}
    body = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {"data": data, "body": body, "body_gz": gzip.compress(body, 6)}


def load():
    """Вміст model_static.json (лише читання!). Перечитується, коли змінився mtime."""
    return _entry(STATIC_PATH, _static_builder)["data"]


def etag():
    """Повний sha1 файлу статики."""
    return _entry(STATIC_PATH, _static_builder)["sha1"]


def static_body():
    """(bytes тіла API-01, gzip-bytes, sha1). Тіло = статика + meta {schema, built_at, static_etag}."""
    entry = _entry(STATIC_PATH, _static_builder)
    return entry["body"], entry["body_gz"], entry["sha1"]


def _manifest_builder(raw):
    manifest = json.loads(raw)
    for part in manifest.get("parts", []):
        h = part.get("hash")
        if not h:
            path = os.path.join(_BASE, "model", "parts", part["key"] + ".glb")
            with open(path, "rb") as fh:
                h = hashlib.sha1(fh.read()).hexdigest()[:12]
        part["file"] = PARTS_URL % (part["key"], h)
    body = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {"body": body, "body_sha1": hashlib.sha1(body).hexdigest()}


def parts_manifest():
    """(bytes, sha1) переписаного manifest.json (parts[].file -> URL з ?v=)."""
    entry = _entry(MANIFEST_PATH, _manifest_builder)
    return entry["body"], entry["body_sha1"]

