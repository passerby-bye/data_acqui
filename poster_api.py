#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple FastAPI backend + static frontend for searching / viewing poster data.
"""

import os
import json
import urllib.parse
from typing import List, Optional
import getpass
import psycopg2
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware


# DB CONFIG (keep in sync with ingest_poster_data_to_db.py)

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


@app.get("/api/figure")
def get_figure(path: str):
    """Serve a figure image."""
    decoded = urllib.parse.unquote(path)
    abs_path = os.path.abspath(decoded)

    if not abs_path.startswith(os.path.abspath(DATA_ROOT_DIR)):
        raise HTTPException(status_code=400, detail="Invalid figure path")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Figure not found")

    return FileResponse(abs_path)


@app.get("/api/poster_image")
def get_poster_image(poster_id: str):
    """Serve the full poster image."""
    if not poster_id:
        raise HTTPException(status_code=400, detail="Missing poster_id")

    filename = f"{poster_id}.png"
    abs_path = os.path.abspath(os.path.join(POSTERS_DIR, filename))

    if not abs_path.startswith(os.path.abspath(POSTERS_DIR)):
        raise HTTPException(status_code=400, detail="Invalid poster_id")
    if not os.path.exists(abs_path):
        return Response(status_code=404)

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
        conditions.append("(title ILIKE %s OR authors::text ILIKE %s OR text_content ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])

    if author:
        # authors is stored as TEXT[]; casting to text makes search more robust
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
        # Extract conference from poster_id or URL
        conference = ""
        if poster_id:
            if poster_id.startswith("ICML") or poster_id.startswith("ICLR"):
                conference = "ICML" if poster_id.startswith("ICML") else "ICLR"
            elif source_url:
                if "icml.cc" in source_url.lower():
                    conference = "ICML"
                elif "iclr.cc" in source_url.lower() or "openreview.net" in source_url.lower():
                    conference = "ICLR"
            elif page_url:
                if "icml.cc" in page_url.lower():
                    conference = "ICML"
                elif "iclr.cc" in page_url.lower() or "openreview.net" in page_url.lower():
                    conference = "ICLR"
        results.append(
            {
                "id": db_id,
                "poster_id": poster_id,
                "title": title,
                "authors": authors or [],
                "source_url": source_url,
                "page_url": page_url,
                "snippet": snippet,
                "conference": conference,
            }
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": results,
    }


@app.get("/api/posters/stats")
def get_poster_stats(
    by: str = Query(..., description="Group by dimension: 'author_count', 'table_count', or 'figure_count'"),
    q: Optional[str] = Query(default=None, description="Filter by keyword in title or text_content"),
    author: Optional[str] = Query(default=None, description="Filter by Author substring"),
):
    """
    Provides aggregated statistics for posters, grouped by the selected dimension,
    optionally filtered by a search query or author.
    """
    valid_groups = ["author_count", "table_count", "figure_count"]
    if by not in valid_groups:
        raise HTTPException(status_code=400, detail=f"Invalid 'by' parameter. Must be one of: {', '.join(valid_groups)}")

    conn = get_db_conn()
    cur = conn.cursor()
    results = []

    # 1. Build the base WHERE clause for filtering (using the same logic as search)
    conditions = []
    params: List = []

    if q:
        conditions.append("(pi.title ILIKE %s OR pi.authors::text ILIKE %s OR pi.text_content ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])

    if author:
        conditions.append("pi.authors::text ILIKE %s")
        params.append(f"%{author}%")
    
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""


    try:
        if by == "author_count":
            # Count author_count directly, filtered by where_clause
            sql = f"""
                SELECT array_length(pi.authors, 1) AS author_count, COUNT(*)
                FROM poster_info pi
                {where_clause}
                AND pi.authors IS NOT NULL AND array_length(pi.authors, 1) IS NOT NULL
                GROUP BY author_count
                ORDER BY author_count;
            """
            cur.execute(sql, params)
            results = [{"dimension": str(r[0]), "count": r[1]} for r in cur.fetchall() if r[0] is not None]
        
        elif by == "table_count":
            # CTE to calculate table count per filtered poster, then group the counts
            sql = f"""
                WITH FilteredPosters AS (
                    SELECT pi.id, pi.poster_id FROM poster_info pi {where_clause}
                ),
                PosterTableCounts AS (
                    SELECT 
                        fp.poster_id, 
                        COUNT(pt.id) AS table_count
                    FROM FilteredPosters fp
                    LEFT JOIN poster_table pt ON fp.id = pt.poster_id
                    GROUP BY fp.poster_id
                )
                SELECT 
                    ptc.table_count AS dimension, 
                    COUNT(*) AS count
                FROM PosterTableCounts ptc
                GROUP BY 1
                ORDER BY 1;
            """
            cur.execute(sql, params)
            results = [{"dimension": str(r[0]), "count": r[1]} for r in cur.fetchall()]

        elif by == "figure_count":
            # CTE to calculate figure count per filtered poster, then group the counts
            sql = f"""
                WITH FilteredPosters AS (
                    SELECT pi.id, pi.poster_id FROM poster_info pi {where_clause}
                ),
                PosterFigureCounts AS (
                    SELECT 
                        fp.poster_id, 
                        COUNT(pf.id) AS figure_count
                    FROM FilteredPosters fp
                    LEFT JOIN poster_figure pf ON fp.id = pf.poster_id
                    GROUP BY fp.poster_id
                )
                SELECT 
                    pfc.figure_count AS dimension, 
                    COUNT(*) AS count
                FROM PosterFigureCounts pfc
                GROUP BY 1
                ORDER BY 1;
            """
            cur.execute(sql, params)
            results = [{"dimension": str(r[0]), "count": r[1]} for r in cur.fetchall()]

    finally:
        cur.close()
        conn.close()

    return {"stats": results, "group_by": by, "q": q, "author": author}


@app.get("/api/posters/{poster_db_id}")
def get_poster_detail(poster_db_id: int):
    # This function remains unchanged
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

    # Determine poster image URL: prefer source_url (web), fallback to local file
    poster_image_url = None
    if source_url:
        # source_url is already a direct image URL from the conference website
        poster_image_url = source_url
    else:
        # Fallback to local file if available
        local_poster_path = os.path.join(POSTERS_DIR, f"{poster_id}.png")
        if os.path.exists(local_poster_path):
            poster_image_url = f"/api/poster_image?poster_id={poster_id}"

    # Extract conference from poster_id or URL
    conference = ""
    if poster_id:
        if poster_id.startswith("ICML") or poster_id.startswith("ICLR"):
            conference = "ICML" if poster_id.startswith("ICML") else "ICLR"
        elif source_url:
            if "icml.cc" in source_url.lower():
                conference = "ICML"
            elif "iclr.cc" in source_url.lower() or "openreview.net" in source_url.lower():
                conference = "ICLR"
        elif page_url:
            if "icml.cc" in page_url.lower():
                conference = "ICML"
            elif "iclr.cc" in page_url.lower() or "openreview.net" in page_url.lower():
                conference = "ICLR"

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
        "poster_image_url": poster_image_url,
        "figures": figure_urls,
        "tables": tables,
        "conference": conference,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("poster_api:app", host="127.0.0.1", port=8000, reload=False)