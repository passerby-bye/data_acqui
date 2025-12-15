# ICML/ICLR Poster Data Extractor and PostgreSQL Ingestion

This project implements a data pipeline to scrape metadata from ICLR and ICML virtual conference posters, structure the AI-parsed content, and load all resulting data into a PostgreSQL database.

---

## 📌 Table of Contents

- [Pipeline Overview](#pipeline-overview)
- [Prerequisites](#prerequisites)
  - [1. Software Environment](#1-software-environment)
  - [2. Python Dependencies](#2-python-dependencies)
  - [3. Database Setup](#3-database-setup)
- [Usage Instructions](#usage-instructions)
  - [Step 1: Data Crawling (Extract)](#step-1-data-crawling-extract)
  - [Step 2: AI Data Preparation](#step-2-ai-data-preparation)
  - [Step 3: Data Ingestion (Load)](#step-3-data-ingestion-load)
- [Verification](#verification)

---

## Pipeline Overview

The project follows a three-stage ETL (Extract, Transform, Load) process:

1. **Extract (Scrapy):** Crawl metadata from conference websites into two separate JSON files, then merge them.  
2. **Transform (External AI):** (Assumed external process) AI parses PDF posters and generates structured files (`result.json`, `result.md`, and cropped images).  
3. **Load (Python Script):** The `ingest_poster_data_to_db.py` script reads the merged metadata and AI results, performing final transformations before loading into PostgreSQL.

---

## Prerequisites

### 1. Software Environment

* **Python:** Version 3.8 or higher  
* **PostgreSQL:** Version 12 or higher  
  *macOS Users:* [Postgres.app](https://postgresapp.com/) is highly recommended

### 2. Python Dependencies

Navigate to the project root directory and install the required libraries:

```bash
pip install scrapy psycopg2-binary
````

### 3. Database Setup

Ensure your PostgreSQL server is running (e.g., started via Postgres.app).

**Create the Database:**

```sql
CREATE DATABASE posters;
```

**Update Configuration:**
Open `ingest_poster_data_to_db.py` and update `DB_CONFIG`:

```python
DB_CONFIG = {
    "dbname": "posters",
    "user": "YOUR_MAC_USERNAME", # MUST be your system username
    "password": "", # Enter your PostgreSQL password if you have set one
    "host": "localhost",
    "port": "5432"
}
```

---

## Usage Instructions

### Step 1: Data Crawling (Extract)

1. **Crawl ICLR Posters**

```bash
scrapy crawl iclr_posters -o iclr_posters.json -t json
```

2. **Crawl ICML Posters**

```bash
scrapy crawl icml_posters -o icml_posters.json -t json
```

3. **Merge JSON Files**

```bash
python merge_json.py
```

> **Result:** A file `merged_posters.json` will be created in the project root

---

### Step 2: AI Data Preparation

This step assumes that PDF posters have already been processed by AI to generate result.json, result.md, and cropped images.

Ensure `processed_data` exists with AI-parsed results:

```
.
├── merged_posters.json
├── processed_data/
│   ├── 29917/
│   │   ├── result.json
│   │   ├── result.md
│   │   └── imgs/
│   │       └── image_0.png
│   └── 28329/
└── ingest_poster_data_to_db.py
```

---

### Step 3: Data Ingestion (Load)

```bash
python ingest_poster_data_to_db.py
```

---

## Verification

1. Connect to PostgreSQL:

```bash
psql -d posters -U YOUR_DB_USERNAME
```

2. List tables:

```sql
\dt
```

3. Query main table:

```sql
SELECT poster_id, title, local_path_md FROM poster_info;
```
