#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple FastAPI backend + static frontend for searching / viewing poster data.

Usage:
  1) Install deps (in project root):
       pip install "fastapi[standard]" psycopg2-binary
  2) Make sure PostgreSQL 'posters' DB is running and ingest_poster_data_to_db.py has been run.
  3) Start server (in project root):
       python poster_api.py
  4) Open in browser:
       http://127.0.0.1:8000
"""

import os
import json
import urllib.parse
import getpass
from typing import List, Optional

import psycopg2
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware


# ------------------------------
# DB CONFIG (keep in sync with ingest_poster_data_to_db.py)
# ------------------------------

DB_CONFIG = {
    "dbname": "posters",
    "user": getpass.getuser(),
    "password": "",  # Update if your PostgreSQL has a password
    "host": "localhost",
    "port": "5432",
}


def get_db_conn():
    return psycopg2.connect(**DB_CONFIG)


app = FastAPI(title="Poster Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------
# Static frontend
# ------------------------------

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")
DATA_ROOT_DIR = os.path.join(PROJECT_ROOT, "icml+iclr_posters", "processed_data")
POSTERS_DIR = os.path.join(PROJECT_ROOT, "icml+iclr_posters", "posters")


@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serve the simple frontend."""
    if not os.path.exists(INDEX_HTML):
        raise HTTPException(status_code=500, detail="index.html not found in ./static")
    return FileResponse(INDEX_HTML)


@app.get("/static/{path:path}")
def serve_static(path: str):
    """Serve static files (JS/CSS, etc)."""
    full_path = os.path.join(STATIC_DIR, path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Static file not found")
    return FileResponse(full_path)


# ------------------------------
# API: Images, Search & Detail
# ------------------------------


@app.get("/api/figure")
def get_figure(path: str):
    """
    Serve a figure image by its original absolute path stored in DB.

    For safety, we:
      1) URL-decode the path
      2) Resolve to absolute path
      3) Ensure it lives under DATA_ROOT_DIR
    """
    decoded = urllib.parse.unquote(path)
    abs_path = os.path.abspath(decoded)

    if not abs_path.startswith(os.path.abspath(DATA_ROOT_DIR)):
        raise HTTPException(status_code=400, detail="Invalid figure path")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Figure not found")

    # Let FileResponse infer content-type from file extension
    return FileResponse(abs_path)


@app.get("/api/poster_image")
def get_poster_image(poster_id: str):
    """
    Serve the full poster image (thumbnail / preview) based on poster_id.

    Looks for a PNG file named {poster_id}.png in icml+iclr_posters/posters.
    """
    if not poster_id:
        raise HTTPException(status_code=400, detail="Missing poster_id")

    filename = f"{poster_id}.png"
    abs_path = os.path.abspath(os.path.join(POSTERS_DIR, filename))

    if not abs_path.startswith(os.path.abspath(POSTERS_DIR)):
        raise HTTPException(status_code=400, detail="Invalid poster_id")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Poster image not found")

    return FileResponse(abs_path)

@app.get("/api/posters/search")
def search_posters(
    q: Optional[str] = Query(default=None, description="Keyword in title or text_content"),
    author: Optional[str] = Query(default=None, description="Author substring"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    offset = (page - 1) * page_size

    conditions = []
    params: List = []

    if q:
        # Global keyword search on title OR authors OR cleaned text_content
        # For better performance later you can switch this to PostgreSQL fulltext.
        conditions.append("(title ILIKE %s OR authors::text ILIKE %s OR text_content ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])

    if author:
        # authors is stored as TEXT[]; casting to text makes search more robust
        # Example value: "{Alice, Bob}" → we just do a substring match on that.
        conditions.append("authors::text ILIKE %s")
        params.append(f"%{author}%")

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    conn = get_db_conn()
    cur = conn.cursor()
    try:
        # total count
        count_sql = f"SELECT COUNT(*) FROM poster_info{where_clause};"
        cur.execute(count_sql, params)
        total = cur.fetchone()[0]

        sql = f"""
        SELECT id, poster_id, title, authors, source_url, page_url, text_content
        FROM poster_info
        {where_clause}
        ORDER BY id
        LIMIT %s OFFSET %s;
        """
        cur.execute(sql, params + [page_size, offset])
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    results = []
    for r in rows:
        db_id, poster_id, title, authors, source_url, page_url, text_content = r
        snippet = (text_content or "")[:260] + ("..." if text_content and len(text_content) > 260 else "")
        results.append(
            {
                "id": db_id,
                "poster_id": poster_id,
                "title": title,
                "authors": authors or [],
                "source_url": source_url,
                "page_url": page_url,
                "snippet": snippet,
            }
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": results,
    }


@app.get("/api/posters/{poster_db_id}")
def get_poster_detail(poster_db_id: int):
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        # main info
        cur.execute(
            """
            SELECT id, poster_id, title, authors, source_url, page_url, text_content,
                   local_path_md, local_path_json
            FROM poster_info
            WHERE id = %s;
            """,
            (poster_db_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Poster not found")

        (
            db_id,
            poster_id,
            title,
            authors,
            source_url,
            page_url,
            text_content,
            local_path_md,
            local_path_json,
        ) = row

        # blocks
        cur.execute(
            """
            SELECT block_label, block_content, block_bbox
            FROM poster_blocks
            WHERE poster_id = %s
            ORDER BY id;
            """,
            (db_id,),
        )
        blocks_rows = cur.fetchall()
        blocks = []
        for blabel, bcontent, bbox in blocks_rows:
            # block_bbox stored as JSONB; psycopg2 returns dict already when using json adaptation
            if isinstance(bbox, str):
                try:
                    bbox_parsed = json.loads(bbox)
                except Exception:
                    bbox_parsed = bbox
            else:
                bbox_parsed = bbox
            blocks.append(
                {
                    "block_label": blabel,
                    "block_content": bcontent,
                    "block_bbox": bbox_parsed,
                }
            )

        # figures
        cur.execute(
            """
            SELECT figure_local_path
            FROM poster_figure
            WHERE poster_id = %s
            ORDER BY id;
            """,
            (db_id,),
        )
        figures_rows = cur.fetchall()

        figure_urls = []
        for (path,) in figures_rows:
            if not path:
                continue
            # HTTP URL pointing to /api/figure
            encoded = urllib.parse.quote(path)
            url = f"/api/figure?path={encoded}"
            figure_urls.append({"path": path, "url": url})

        # tables
        cur.execute(
            """
            SELECT table_markdown
            FROM poster_table
            WHERE poster_id = %s
            ORDER BY id;
            """,
            (db_id,),
        )
        tables_rows = cur.fetchall()
        tables = [t[0] for t in tables_rows]

    finally:
        cur.close()
        conn.close()

    return {
        "id": db_id,
        "poster_id": poster_id,
        "title": title,
        "authors": authors or [],
        "source_url": source_url,
        "page_url": page_url,
        "text_content": text_content,
        "local_path_md": local_path_md,
        "local_path_json": local_path_json,
        "blocks": blocks,
        "poster_image_url": f"/api/poster_image?poster_id={poster_id}",
        "figures": figure_urls,
        "tables": tables,
    }


if __name__ == "__main__":
    # Use FastAPI's built-in runner (via fastapi[standard]) to simplify usage.
    import uvicorn

    uvicorn.run("poster_api:app", host="127.0.0.1", port=8000, reload=False)


