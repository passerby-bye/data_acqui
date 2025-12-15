# ICML/ICLR Poster Data Extractor and PostgreSQL Ingestion

This project implements a data pipeline to scrape metadata from ICLR and ICML virtual conference posters, structure the AI-parsed content, and load all resulting data into a PostgreSQL database.

---

## Table of Contents

- [Pipeline Overview](#pipeline-overview)
- [Prerequisites](#prerequisites)
  - [1. Software Environment](#1-software-environment)
  - [2. Python Dependencies](#2-python-dependencies)
  - [3. Database Setup](#3-database-setup)
- [Usage Instructions](#usage-instructions)
  - [Step 1: Data Crawling (Extract)](#step-1-data-crawling-extract)
  - [Step 2: Data Preparation](#step-2-data-preparation)
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
pip install scrapy psycopg2-binary "fastapi[standard]" paddleocr
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
    "user": "YOUR_DB_USERNAME", # MUST be your system username
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

Run to combine the two output files into a single, unified file needed by the ingestion script.

```bash
python merge_json.py
```

> **Result:** A file `merged_posters.json` will be created in the project root

---

### Step 2: Data Preparation

This step assumes that PDF posters have already been processed by AI to generate `result.json`, `result.md`, and cropped images.
We tried many methods, and after considering both effectiveness and cost, we finally chose [PaddlePaddleOCR](https://huggingface.co/PaddlePaddle/PaddleOCR-VL).
Processing a single poster may take 40-60 seconds, and the images may be split into Markdown and JSON formats. The `imgs` folder stores the segmented images recognized from the poster.

```bash
# The following command installs the PaddlePaddle version for CUDA 12.6. For other CUDA versions and the CPU version, please refer to https://www.paddlepaddle.org.cn/en/install/quick?docurl=/documentation/docs/en/develop/install/pip/linux-pip_en.html
python -m pip install paddlepaddle-gpu==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
python -m pip install -U "paddleocr[doc-parser]"
# For Linux systems, run:
python -m pip install https://paddle-whl.bj.bcebos.com/nightly/cu126/safetensors/safetensors-0.6.2.dev0-cp38-abi3-linux_x86_64.whl
# For Windows systems, run:
python -m pip install https://xly-devops.cdn.bcebos.com/safetensors-nightly/safetensors-0.6.2.dev0-cp38-abi3-win_amd64.whl

````
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

Run the main script to initialize the database tables and ingest all structured data.

```bash
python ingest_poster_data_to_db.py
```

---

## Verification

Upon successful execution, the script will print `3. All Posters Processed`. You can verify the data using the `psql` command-line tool.

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

### Interactive Visualization Interface

From the project root directory, run:

```bash
python poster_api.py
```

If everything is configured correctly, the terminal will output something like:

```bash
INFO:     Uvicorn running on http://127.0.0.1:8000 ...
```

### Access the Frontend in Your Browser
Open any browser and navigate to:
```bash
http://127.0.0.1:8000
```

You should now see the full Poster Explorer interface.
