#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1. Reads AI-processed data (result.json, result.md, imgs/) from local folders.
2. Combines extracted data with original metadata (from merged_posters.json).
3. Stores structured content and local file paths into PostgreSQL database.
"""

import os
import re
import json
import psycopg2
import getpass

# Configuration

# Set this directory as the parent directory containing all poster ID folders (e.g., '29917', '28451')
DATA_ROOT_DIR = "./processed_data" 
MERGED_JSON = "./merged_posters.json" 

DB_CONFIG = {
    "dbname": "posters",
    "user": getpass.getuser(),
    "password": "", # Modify according to your PostgreSQL configuration
    "host": "localhost",
    "port": "5432"
}

# Database Initialization (Updated SQL)

CREATE_TABLES_SQL = """
-- 1. Main Table: Stores core metadata and cleaned text content
CREATE TABLE IF NOT EXISTS poster_info (
    id SERIAL PRIMARY KEY,
    poster_id VARCHAR(50) UNIQUE,  -- The unique ID of the poster (e.g., '29917')
    title TEXT,
    authors TEXT[],
    source_url TEXT,
    page_url TEXT,
    text_content TEXT, -- Cleaned version of the full Markdown text
    
    -- Local File System paths for original files and Markdown
    local_path_md TEXT,
    local_path_json TEXT
);

-- 2. Blocks Table: Stores all structural blocks identified by AI, using JSONB for bounding boxes
CREATE TABLE IF NOT EXISTS poster_blocks (
    id SERIAL PRIMARY KEY,
    poster_id INTEGER REFERENCES poster_info(id) ON DELETE CASCADE,
    block_label VARCHAR(50),      -- e.g., 'doc_title', 'text', 'chart_box'
    block_content TEXT,
    block_bbox JSONB              -- Stores bounding box coordinates [x1, y1, x2, y2]
);

-- 3. Figure Table: Stores local paths for cropped figures
CREATE TABLE IF NOT EXISTS poster_figure (
    id SERIAL PRIMARY KEY,
    poster_id INTEGER REFERENCES poster_info(id) ON DELETE CASCADE,
    figure_local_path TEXT        -- Stores the local path of the image in the imgs folder
);

-- 4. Table Table: Stores extracted Markdown tables
CREATE TABLE IF NOT EXISTS poster_table (
    id SERIAL PRIMARY KEY,
    poster_id INTEGER REFERENCES poster_info(id) ON DELETE CASCADE,
    table_markdown TEXT
);
"""


# Step 1: Data Parsing Helpers

def normalize_authors(auth):
    """Ensures the authors field is a list and standardizes the processing."""
    if not auth:
        return []
    if isinstance(auth, list):
        return [a.strip() for a in auth]
    if isinstance(auth, str):
        # Supports various delimiters
        parts = re.split(r",|;|/|\band\b|\·", auth)
        return [p.strip() for p in parts if p.strip()]
    return []

def clean_html_tags(text):
    """Remove raw HTML tags."""
    return re.sub(r'<[^>]+>', '', text)

def sanitize_cell(cell_html):
    """Remove tags and fix line breaks in table cells."""
    cell = re.sub(r"<br\s*/?>", "  \n", cell_html)
    cell = re.sub(r"<[^>]+>", "", cell)
    return cell.strip()

def html_table_to_markdown(html):
    """Convert HTML table → aligned GitHub-style Markdown table."""
    rows = re.findall(r"<tr[\s\S]*?</tr>", html, flags=re.IGNORECASE)
    table = []
    for r in rows:
        cells = re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", r, flags=re.IGNORECASE)
        if cells:
            table.append([sanitize_cell(c) for c in cells])

    if not table:
        return ""

    header = table[0]
    data = table[1:]
    cols = len(header)

    # Compute column widths for alignment
    def col_width(i):
        items = [header[i]] + [row[i] if i < len(row) else "" for row in data]
        return max(len(x) for x in items)

    widths = [col_width(i) for i in range(cols)]

    def format_row(row):
        return "|" + "|".join(f" {row[i].ljust(widths[i])} " if i < len(row) else f" {'':{widths[i]}} " for i in range(cols)) + "|"

    header_line = format_row(header)
    separator = "|" + "|".join(f" {'-' * widths[i]} " for i in range(cols)) + "|"
    data_lines = [format_row(row) for row in data]

    return "\n".join([header_line, separator] + data_lines)


def clean_text(text):
    """Basic cleaning of extracted OCR text (remove noise and spacing artifacts)."""
    text = re.sub(r'<[^>]+>', '', text)              # remove remaining HTML tags
    text = re.sub(r'\s+', ' ', text)                 # collapse whitespace
    text = re.sub(r'\|+', ' ', text)                 # remove table pipes
    text = re.sub(r'(?:\+|=|-){5,}', '', text)       # remove long lines
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_markdown(md_text):
    """Extract pure text (no <img> or <table>), figures, and tables separately."""
    # Remove <img> and collect figure URLs
    figures = re.findall(r'<img[^>]+src="([^"]+)"', md_text)
    md_text_noimg = re.sub(r'<img[^>]*>', '', md_text)

    # Remove <table> but keep them separately
    tables_html = re.findall(r'<table[\s\S]*?</table>', md_text_noimg)
    md_text_notable = re.sub(r'<table[\s\S]*?</table>', '', md_text_noimg)
    tables = [html_table_to_markdown(t) for t in tables_html]

    # Raw text before cleanup
    raw_text = clean_html_tags(md_text_notable)

    # Cleaned text
    cleaned_text = clean_text(raw_text)

    return raw_text.strip(), cleaned_text.strip(), figures, tables

# Main Pipeline
def main():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Database connection failed. Check DB_CONFIG and PostgreSQL service status: {e}")
        return
        
    cur = conn.cursor()

    print(" 1. Database Initialization")
    try:
        # Drop tables in dependency order to allow clean reset
        cur.execute("DROP TABLE IF EXISTS poster_figure CASCADE;")
        cur.execute("DROP TABLE IF EXISTS poster_table CASCADE;")
        cur.execute("DROP TABLE IF EXISTS poster_blocks CASCADE;")
        cur.execute("DROP TABLE IF EXISTS poster_info CASCADE;")
        cur.execute(CREATE_TABLES_SQL)
        conn.commit()
        print("Database tables created/reset successfully.")
    except Exception as e:
        print(f"Failed to create database tables: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return

    print("\n 2. Reading Metadata and Processing Files")
    if not os.path.exists(MERGED_JSON):
        print(f"Missing original metadata file: {MERGED_JSON}")
        return

    try:
        with open(MERGED_JSON, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"Could not read or parse {MERGED_JSON}: {e}")
        return
        
    if not os.path.exists(DATA_ROOT_DIR):
        print(f"Data root directory not found: {DATA_ROOT_DIR}")
        return

    # Iterate through poster ID folders
    poster_ids = [d for d in os.listdir(DATA_ROOT_DIR) if os.path.isdir(os.path.join(DATA_ROOT_DIR, d))]
    print(f"Found {len(poster_ids)} processed poster folders.\n")

    for idx, poster_id in enumerate(poster_ids, 1):
        print(f"[{idx}/{len(poster_ids)}] Processing {poster_id} ...")
        poster_root = os.path.join(DATA_ROOT_DIR, poster_id)

        json_path = os.path.join(poster_root, 'result.json')
        md_path = os.path.join(poster_root, 'result.md')
        imgs_dir = os.path.join(poster_root, 'imgs')

        # Check file integrity
        if not all(os.path.exists(p) for p in [json_path, md_path]):
            print(f"Missing result.json or result.md files, skipping.")
            continue

        try:
            # 1. Read AI result files
            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()
            
            with open(json_path, "r", encoding="utf-8") as f:
                ai_data = json.load(f)
                ai_blocks = ai_data.get('parsing_res_list', [])

            # 2. Match old metadata
            record = next((m for m in metadata if str(m.get("poster_id")) == poster_id or (m.get("local_png_path") and f"{poster_id}.png" in m["local_png_path"])), None)

            if not record:
                print(f"Original metadata record not found, skipping.")
                continue
            
            # 3. Data extraction and cleaning
            title = record.get("title")
            authors = normalize_authors(record.get("authors"))
            source_url = record.get("source_url")
            page_url = record.get("page_url")
            
            # Extract text, figures, and tables from result.md
            raw_text_md, cleaned_text_md, figures_md_links, tables = parse_markdown(md_text) 
            
            # Collect local paths for cropped images from imgs/ folder
            figure_paths = []
            if os.path.exists(imgs_dir):
                figure_paths = [os.path.abspath(os.path.join(imgs_dir, f)) for f in os.listdir(imgs_dir) if f.endswith(('.jpg', '.png'))]
            
            # 4. Database Insertion
            
            # 4.1 Insert poster_info (Main info)
            cur.execute("""
                INSERT INTO poster_info (poster_id, title, authors, source_url, page_url, text_content, local_path_md, local_path_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (poster_id, title, authors, source_url, page_url, cleaned_text_md, os.path.abspath(md_path), os.path.abspath(json_path)))
            poster_db_id = cur.fetchone()[0]

            # 4.2 Insert poster_blocks (All structural blocks)
            for block in ai_blocks:
                cur.execute("""
                    INSERT INTO poster_blocks (poster_id, block_label, block_content, block_bbox)
                    VALUES (%s, %s, %s, %s);
                """, (poster_db_id, block['block_label'], block['block_content'], json.dumps(block['block_bbox'])))

            # 4.3 Insert poster_figure (Using local paths)
            for fig_path in figure_paths:
                cur.execute("INSERT INTO poster_figure (poster_id, figure_local_path) VALUES (%s, %s)", (poster_db_id, fig_path))
            
            # 4.4 Insert poster_table
            for tb in tables:
                cur.execute("INSERT INTO poster_table (poster_id, table_markdown) VALUES (%s, %s)", (poster_db_id, tb))
            
            conn.commit()
            print(f"Successfully inserted into RDBMS: Title={title[:30]}... (DB ID={poster_db_id})\n")

        except Exception as e:
            print(f"Database insertion failed for {poster_id}: {e}")
            conn.rollback()

    cur.close()
    conn.close()
    print(" 3. All Posters Processed")

if __name__ == "__main__":
    main()