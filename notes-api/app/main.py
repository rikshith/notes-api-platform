"""Notes API: a deliberately small app for practising DevOps/SRE work.

Config comes only from environment variables:
  DATABASE_URL        default sqlite:///./notes.db (use postgresql://... in real runs)
  REDIS_URL           optional, e.g. redis://localhost:6379/0 (cache is skipped if unset)
  CACHE_TTL_SECONDS   default 60
  ERROR_RATE          0.0-1.0, fraction of /notes requests that fail (simulates a bad release)
  EXTRA_LATENCY_MS    added delay on /notes requests (simulates a slow dependency)
"""
import os
import random
import time
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notes.db")
REDIS_URL = os.getenv("REDIS_URL", "")
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "60"))
MAX_LEAK_MB = int(os.getenv("MAX_LEAK_MB", "512"))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

cache = (
    redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
    if REDIS_URL
    else None
)

_leak = []  # holds memory for the /leak drill


class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class NoteIn(BaseModel):
    title: str
    body: str = ""


def _chaos():
    """Apply env-driven latency and errors to normal traffic."""
    delay = int(os.getenv("EXTRA_LATENCY_MS", "0"))
    if delay:
        time.sleep(delay / 1000)
    if random.random() < float(os.getenv("ERROR_RATE", "0")):
        raise HTTPException(status_code=500, detail="injected failure")


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(10):  # the DB may still be starting
        try:
            Base.metadata.create_all(engine)
            break
        except Exception:
            if attempt == 9:
                raise
            time.sleep(2)
    yield


app = FastAPI(title="Notes API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
def health():
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: dependencies are reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    if cache is not None:
        try:
            cache.ping()
        except Exception:
            raise HTTPException(status_code=503, detail="cache unavailable")
    return {"status": "ready"}


@app.post("/notes", status_code=201)
def create_note(payload: NoteIn):
    _chaos()
    with SessionLocal() as db:
        note = Note(title=payload.title, body=payload.body)
        db.add(note)
        db.commit()
        db.refresh(note)
        return {"id": note.id, "title": note.title, "body": note.body}


@app.get("/notes")
def list_notes(limit: int = 50):
    _chaos()
    with SessionLocal() as db:
        rows = db.query(Note).order_by(Note.id.desc()).limit(min(limit, 200)).all()
        return [{"id": n.id, "title": n.title} for n in rows]


@app.get("/notes/{note_id}")
def get_note(note_id: int):
    _chaos()
    key = f"note:{note_id}"
    if cache is not None:
        try:
            hit = cache.get(key)
            if hit:
                return {"source": "cache", **__import__("json").loads(hit)}
        except Exception:
            pass  # cache failure should not break reads
    with SessionLocal() as db:
        note = db.get(Note, note_id)
        if not note:
            raise HTTPException(status_code=404, detail="not found")
        data = {"id": note.id, "title": note.title, "body": note.body}
    if cache is not None:
        try:
            cache.setex(key, CACHE_TTL, __import__("json").dumps(data))
        except Exception:
            pass
    return {"source": "db", **data}


# ---- Failure drills: use these to practise incident response ----

@app.get("/slow")
def slow(ms: int = 1000):
    """Latency drill: responds after `ms` milliseconds (max 30000)."""
    time.sleep(min(ms, 30000) / 1000)
    return {"slept_ms": min(ms, 30000)}


@app.get("/error")
def error(rate: float = 1.0):
    """Error drill: returns HTTP 500 with probability `rate`."""
    if random.random() < rate:
        raise HTTPException(status_code=500, detail="induced error")
    return {"status": "ok"}


@app.get("/cpu")
def cpu(seconds: int = 5):
    """CPU drill: burns one core for `seconds` (max 60)."""
    end = time.time() + min(seconds, 60)
    while time.time() < end:
        sum(i * i for i in range(10_000))
    return {"burned_seconds": min(seconds, 60)}


@app.get("/leak")
def leak(mb: int = 50):
    """Memory drill: allocates and keeps `mb` MB, up to MAX_LEAK_MB in total."""
    held = sum(len(b) for b in _leak) // (1024 * 1024)
    if held + mb > MAX_LEAK_MB:
        raise HTTPException(status_code=400, detail=f"limit reached ({held} MB held)")
    _leak.append(bytearray(mb * 1024 * 1024))
    return {"held_mb": held + mb}


@app.post("/leak/clear")
def leak_clear():
    _leak.clear()
    return {"held_mb": 0}
