#!/usr/bin/env python3
"""
Parse documents from data/files/ directory and store in documents.db

Supports:
- PDF files (.pdf)
- Text files (.txt)
- Markdown files (.md)

The script can be run multiple times safely - it checks for existing filenames
and skips already processed files.
"""

import os
import sqlite3
from pathlib import Path

# pip install PyPDF2
import PyPDF2

from utils import count_tokens


def parse_pdf(file_path):
    """Extract text content from PDF file"""
    content = ""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                content += page.extract_text()
    except Exception as e:
        print(f"  Error parsing PDF {file_path}: {str(e)}")
        return None

    return content


def parse_txt(file_path):
    """Read text content from TXT file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except Exception as e:
        print(f"  Error reading TXT {file_path}: {str(e)}")
        return None

    return content


def parse_md(file_path):
    """Read text content from Markdown file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except Exception as e:
        print(f"  Error reading MD {file_path}: {str(e)}")
        return None

    return content


def process_document(file_path, conn):
    """Process a single document and insert into database"""
    cursor = conn.cursor()

    filename = os.path.basename(file_path)
    file_extension = os.path.splitext(file_path)[1].lower()

    # Check if file already exists in database
    cursor.execute(
        "SELECT COUNT(*) FROM documents WHERE filename = ?",
        (filename,)
    )

    if cursor.fetchone()[0] > 0:
        print(f"  Already exists: {filename}")
        return False

    # Parse content based on file type
    content = None
    if file_extension == '.pdf':
        content = parse_pdf(file_path)
    elif file_extension == '.txt':
        content = parse_txt(file_path)
    elif file_extension == '.md':
        content = parse_md(file_path)
    else:
        print(f"  Unsupported format: {filename}")
        return False

    if content is None:
        return False

    # Remove NUL characters that can cause SQLite issues
    content = content.replace('\x00', '')

    # Strip leading and trailing whitespace
    content = content.strip()
    tokens_count = count_tokens(content)

    # Insert into database
    try:
        cursor.execute(
            """INSERT INTO documents (filename, content, tokens_count, hit_count)
               VALUES (?, ?, ?, ?)""",
            (filename, content, tokens_count, 0)
        )
        conn.commit()
        print(f"  Successfully imported: {filename}")
        return True
    except sqlite3.Error as e:
        print(f"  Database error for {filename}: {e}")
        conn.rollback()
        return False


def parse_documents():
    """Main function to parse all documents from data/files/ directory"""

    # Ensure directories exist
    files_dir = Path("data/files")
    if not files_dir.exists():
        print(f"  Directory does not exist: {files_dir}")
        print(f"  Creating directory: {files_dir}")
        files_dir.mkdir(parents=True, exist_ok=True)
        return

    # Connect to database
    db_path = "data/documents.db"
    if not Path(db_path).exists():
        print(f"  Database does not exist: {db_path}")
        print(f"  Please run migrate_documents_db.py first")
        return

    conn = sqlite3.connect(db_path)

    # Get all supported files
    supported_extensions = ['.pdf', '.txt', '.md']
    files = []
    for ext in supported_extensions:
        files.extend(files_dir.glob(f'*{ext}'))

    if not files:
        print(f"No files found in {files_dir}")
        conn.close()
        return

    print(f"Found {len(files)} file(s) in {files_dir}")
    print()

    success_count = 0
    skip_count = 0
    error_count = 0

    for file_path in sorted(files):
        result = process_document(str(file_path), conn)
        if result:
            success_count += 1
        elif result is False:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM documents WHERE filename = ?",
                (os.path.basename(file_path),)
            )
            if cursor.fetchone()[0] > 0:
                skip_count += 1
            else:
                error_count += 1

    conn.close()

    print()
    print(f"Summary:")
    print(f"  Imported: {success_count}")
    print(f"  Skipped (already exists): {skip_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total: {len(files)}")


if __name__ == "__main__":
    parse_documents()
