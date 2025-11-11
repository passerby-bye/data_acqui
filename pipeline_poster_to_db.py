#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_poster_to_db.py

Description:
1. Use an AI API to extract Markdown text from local poster PNGs
2. Combine extracted Markdown with metadata (from merged_posters.json)
3. Store the structured content into PostgreSQL database
"""

import os
import re
import json
import psycopg2
from gradio_client import Client, handle_file
import getpass


# Configuration

AI_API_URL = "https://app-u613z0mda075e806.aistudio-app.com/"
POSTER_DIR = "./posters"
MARKDOWN_DIR = "./markdowns"
MERGED_JSON = "./merged_posters.json"

DB_CONFIG = {
    "dbname": "posters",
    "user": getpass.getuser(),
    "password": "",
    "host": "localhost",
    "port": "5432"
}

# Database Initialization

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS poster_info (
    id SERIAL PRIMARY KEY,
    title TEXT,
    authors TEXT[],
    source_url TEXT,
    page_url TEXT,
    text_content TEXT
);

CREATE TABLE IF NOT EXISTS poster_text (
    id SERIAL PRIMARY KEY,
    poster_id INTEGER REFERENCES poster_info(id) ON DELETE CASCADE,
    raw_text TEXT,
    cleaned_text TEXT
);

CREATE TABLE IF NOT EXISTS poster_figure (
    id SERIAL PRIMARY KEY,
    poster_id INTEGER REFERENCES poster_info(id) ON DELETE CASCADE,
    figure_url TEXT
);

CREATE TABLE IF NOT EXISTS poster_table (
    id SERIAL PRIMARY KEY,
    poster_id INTEGER REFERENCES poster_info(id) ON DELETE CASCADE,
    table_markdown TEXT
);
"""

# Step 1: Markdown Extraction via API

def generate_markdown(client, image_path):
    """Send PNG to AI API and save the Markdown output."""
    filename = os.path.basename(image_path)
    md_path = os.path.join(MARKDOWN_DIR, filename.replace(".png", ".md"))
    os.makedirs(MARKDOWN_DIR, exist_ok=True)

    if os.path.exists(md_path):
        print(f"Markdown already exists for {filename}")
        return md_path

    print(f"Extracting text for {filename} ...")
    try:
        md, _, _ = client.predict(
            fp=handle_file(image_path),
            use_chart=True,
            use_unwarping=True,
            use_orientation=True,
            api_name="/parse_doc_router"
        )
        with open(md_path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(md)
        print(f"Saved Markdown: {md_path}")
        return md_path
    except Exception as e:
        print(f"Failed to extract Markdown for {filename}: {e}")
        return None


# Step 2: Markdown Parsing Helpers

def clean_html_tags(text):
    """Remove raw HTML tags."""
    return re.sub(r'<[^>]+>', '', text)

def normalize_authors(auth):
    """Ensure author field is a list."""
    if not auth:
        return []
    if isinstance(auth, list):
        return [a.strip() for a in auth]
    if isinstance(auth, str):
        parts = re.split(r",|;|/|\band\b", auth)
        return [p.strip() for p in parts if p.strip()]
    return []

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


# Step 3: Database Insertion

def insert_poster(cur, title, authors, source_url, page_url, text):
    cur.execute("""
        INSERT INTO poster_info (title, authors, source_url, page_url, text_content)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (title, authors, source_url, page_url, text))
    row = cur.fetchone()
    return row[0] if row else None


def insert_poster_text(cur, poster_id, raw_text, cleaned_text):
    cur.execute("""
        INSERT INTO poster_text (poster_id, raw_text, cleaned_text)
        VALUES (%s, %s, %s);
    """, (poster_id, raw_text, cleaned_text))


# Main Pipeline

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("Resetting database...")
    cur.execute("DROP TABLE IF EXISTS poster_figure CASCADE;")
    cur.execute("DROP TABLE IF EXISTS poster_table CASCADE;")
    cur.execute("DROP TABLE IF EXISTS poster_text CASCADE;")
    cur.execute("DROP TABLE IF EXISTS poster_info CASCADE;")
    cur.execute(CREATE_TABLES_SQL)
    conn.commit()

    try:
        client = Client(AI_API_URL)
        print(f"Connected to API: {AI_API_URL}")
    except Exception as e:
        print(f"API connection failed: {e}")
        return

    if not os.path.exists(MERGED_JSON):
        print(f"Missing {MERGED_JSON}")
        return

    with open(MERGED_JSON, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    posters = [p for p in os.listdir(POSTER_DIR) if p.endswith(".png")]
    print(f"Found {len(posters)} posters.\n")

    for idx, fname in enumerate(posters, 1):
        print(f"[{idx}/{len(posters)}] Processing {fname} ...")
        image_path = os.path.join(POSTER_DIR, fname)

        md_path = generate_markdown(client, image_path)
        if not md_path or not os.path.exists(md_path):
            conn.rollback()
            continue

        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        # Find corresponding JSON record
        fname_lower = fname.lower()
        record = None
        for m in metadata:
            if fname_lower in m.get("local_png_path", "").lower():
                record = m
                break

        if record:
            title = record.get("title")
            authors = normalize_authors(record.get("authors"))
            source_url = record.get("source_url")
            page_url = record.get("page_url")
        else:
            print(f"No metadata found for {fname}")
            conn.rollback()
            continue

        raw_text, cleaned_text, figures, tables = parse_markdown(md_text)

        try:
            poster_id = insert_poster(cur, title, authors, source_url, page_url, cleaned_text)
            if poster_id:
                insert_poster_text(cur, poster_id, raw_text, cleaned_text)
                for fig in figures:
                    cur.execute("INSERT INTO poster_figure (poster_id, figure_url) VALUES (%s, %s)", (poster_id, fig))
                for tb in tables:
                    cur.execute("INSERT INTO poster_table (poster_id, table_markdown) VALUES (%s, %s)", (poster_id, tb))
                conn.commit()
                print(f"Inserted: {title[:60] if title else 'Untitled'} (ID={poster_id})\n")
            else:
                print(f"Skipped duplicate {fname}\n")
                conn.rollback()
        except Exception as e:
            print(f"Insert failed for {fname}: {e}")
            conn.rollback()

    cur.close()
    conn.close()
    print("All posters processed successfully !!!")

if __name__ == "__main__":
    main()
