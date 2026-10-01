"""MCP-сервер поиска по базе знаний ITnet2 (Qdrant: ite_docs, ite_code).

Поиск гибридный: плотные векторы paraphrase-multilingual-mpnet-base-v2
(fastembed 0.7.x, mean pooling — как при индексации) + разреженные Qdrant/bm25,
слияние через RRF. Настройки — через переменные окружения, см. README.md.
"""
import logging
import os
import sys
import threading
import warnings

from qdrant_client import QdrantClient, models as m

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
    from mcp.server.fastmcp.exceptions import ToolError

warnings.filterwarnings("ignore", category=UserWarning)
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
log = logging.getLogger("ite-rag")

QDRANT_URL = os.getenv("QDRANT_URL", "http://167.233.49.46:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
DENSE_MODEL = os.getenv("ITE_DENSE_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
BM25_MODEL = os.getenv("ITE_BM25_MODEL", "Qdrant/bm25")
BM25_LANGUAGE = os.getenv("ITE_BM25_LANGUAGE", "english")

COLLECTIONS = {"docs": "ite_docs", "code": "ite_code"}
TEXT_LIMIT = 1200

INSTRUCTIONS = """\
База знаний ERP-системы ITnet2 (ІТ-Ентерпрайз). Две коллекции:
- docs (ite_docs): справка из CHM (source=help), описания форм и таблиц с полями
  (source=forms), пошаговые инструкции по бухучёту (source=instr), обзоры библиотек
  (source=libs), журнал находок прошлой работы с веб-клиентом из CLAUDE.md (source=claude).
- code (ite_code): методы и классы серверного кода ITnet2 (kind=method|class) с
  сигнатурами, namespace, файлом и таблицами БД (фильтр table, например DMZ, KDK).

Порядок работы: ite_overview — понять, что есть и какие значения фильтров;
ite_search — найти фрагменты по теме; ite_get_document — дочитать документ целиком
по doc_id из результатов поиска. Таблицы ищите по коду (DMZ, KSM) — это хорошо
работает и в docs (source=forms), и в code (table=...)."""

mcp = _Server("ite-rag", instructions=INSTRUCTIONS)

_qc = None
_models = {}
_models_lock = threading.Lock()


def client():
    global _qc
    if _qc is None:
        _qc = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60, prefer_grpc=False)
    return _qc


def embedders():
    """Модели грузятся один раз; первая загрузка скачивает ~1 ГБ."""
    with _models_lock:
        if not _models:
            from fastembed import SparseTextEmbedding, TextEmbedding
            _models["dense"] = TextEmbedding(DENSE_MODEL)
            _models["bm25"] = SparseTextEmbedding(BM25_MODEL, language=BM25_LANGUAGE)
    return _models["dense"], _models["bm25"]


def _collections(collection):
    if collection == "all":
        return list(COLLECTIONS.values())
    if collection not in COLLECTIONS:
        raise ToolError(f"collection должен быть одним из: {', '.join([*COLLECTIONS, 'all'])}")
    return [COLLECTIONS[collection]]


def _filter(source, kind, library, table, doc_id=None):
    must = [m.FieldCondition(key=k, match=m.MatchValue(value=v))
            for k, v in (("source", source), ("kind", kind), ("library", library),
                         ("tables", table), ("doc_id", doc_id)) if v not in (None, "")]
    return m.Filter(must=must) if must else None


def _hit(point, collection, full=False):
    pl = point.payload or {}
    text = pl.get("text", "")
    item = {
        "collection": collection,
        "doc_id": pl.get("doc_id"),
        "chunk_id": pl.get("chunk_id"),
        "source": pl.get("source"),
        "kind": pl.get("kind"),
        "title": pl.get("title"),
        "doc_title": pl.get("doc_title"),
        "path": pl.get("path"),
        "text": text if full or len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT] + " …",
    }
    for k in ("library", "tables", "nid"):
        if pl.get(k):
            item[k] = pl[k]
    if getattr(point, "score", None) is not None:
        item["score"] = round(point.score, 4)
    return item


@mcp.tool()
def ite_search(query: str, collection: str = "all", limit: int = 8, mode: str = "hybrid",
               source: str = "", kind: str = "", library: str = "", table: str = "") -> dict:
    """Поиск по базе знаний ITnet2.

    query: вопрос или ключевые слова на любом языке (укр/рус/англ), имена классов,
        методов, кодов таблиц (DMZ, KDK5).
    collection: docs | code | all.
    limit: сколько фрагментов вернуть на коллекцию (1–30).
    mode: hybrid (смысл + слова, по умолчанию) | dense (только смысл) | bm25 (только слова,
        лучше для точных имён и кодов).
    source: фильтр docs — help | forms | instr | libs | claude; в code — code.
    kind: help | fields | form | finding | lib | step | note | lead (docs); method | class (code).
    library: точное имя библиотеки, например ITnet2.Server.BusinessLogic.HR.
    table: код таблицы БД (только code), например DMZ.
    """
    if mode not in ("hybrid", "dense", "bm25"):
        raise ToolError("mode: hybrid | dense | bm25")
    limit = max(1, min(int(limit), 30))
    dense, bm25 = embedders()
    dv = next(dense.query_embed(query)).tolist()
    s = next(bm25.query_embed(query))
    sv = m.SparseVector(indices=s.indices.tolist(), values=s.values.tolist())
    flt = _filter(source, kind, library, table)

    results = []
    for col in _collections(collection):
        if mode == "hybrid":
            res = client().query_points(
                col,
                prefetch=[m.Prefetch(query=dv, using="dense", limit=limit * 4, filter=flt),
                          m.Prefetch(query=sv, using="bm25", limit=limit * 4, filter=flt)],
                query=m.FusionQuery(fusion=m.Fusion.RRF), limit=limit, with_payload=True)
        else:
            res = client().query_points(col, query=dv if mode == "dense" else sv, using=mode,
                                        query_filter=flt, limit=limit, with_payload=True)
        results += [_hit(p, col) for p in res.points]
    return {"query": query, "mode": mode, "count": len(results), "results": results}


@mcp.tool()
def ite_get_document(doc_id: int, collection: str = "docs", max_chunks: int = 200) -> dict:
    """Все фрагменты одного документа по doc_id (из результатов ite_search), по порядку.

    collection: docs | code. max_chunks ограничивает объём ответа.
    """
    col = _collections(collection)[0]
    points, offset = [], None
    while len(points) < max_chunks:
        batch, offset = client().scroll(col, scroll_filter=_filter(None, None, None, None, int(doc_id)),
                                        limit=min(256, max_chunks - len(points)), offset=offset,
                                        with_payload=True, with_vectors=False)
        points += batch
        if offset is None:
            break
    points.sort(key=lambda p: int((p.payload or {}).get("chunk_id") or p.id))
    chunks = [_hit(p, col, full=True) for p in points]
    head = chunks[0] if chunks else {}
    return {
        "doc_id": doc_id, "collection": col, "doc_title": head.get("doc_title"),
        "path": head.get("path"), "source": head.get("source"), "chunks": len(chunks),
        "truncated": offset is not None,
        "text": "\n\n".join(_body(c) if i else c["text"] for i, c in enumerate(chunks)),
    }


def _body(chunk):
    """Фрагменты начинаются с заголовка документа — при склейке он лишний."""
    first, _, rest = chunk["text"].partition("\n")
    return rest if rest and first.strip() in (chunk.get("title"), chunk.get("doc_title")) else chunk["text"]


@mcp.tool()
def ite_overview(collection: str = "all", key: str = "", limit: int = 40) -> dict:
    """Что лежит в базе: число фрагментов и распределение по полю.

    collection: docs | code | all. key: source | kind | library | tables (только code);
    пусто — сводка по source и kind. Удобно, чтобы узнать значения для фильтров ite_search.
    """
    keys = [key] if key else ["source", "kind"]
    out = {}
    for col in _collections(collection):
        info = client().get_collection(col)
        facets = {}
        for k in keys:
            try:
                hits = client().facet(col, key=k, limit=max(1, min(int(limit), 200))).hits
                facets[k] = {str(h.value): h.count for h in hits}
            except Exception as e:  # поле без индекса в этой коллекции
                facets[k] = f"недоступно: {e.__class__.__name__}"
        out[col] = {"points": info.points_count, "facets": facets}
    return out


def _warmup():
    try:
        embedders()
    except Exception:
        log.exception("не удалось загрузить модели эмбеддингов")


def main():
    if not QDRANT_API_KEY:
        sys.exit("QDRANT_API_KEY не задан")
    threading.Thread(target=_warmup, daemon=True).start()
    mcp.run("stdio")


if __name__ == "__main__":
    main()
