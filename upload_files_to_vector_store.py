# https://platform.openai.com/docs/guides/retrieval
# https://platform.openai.com/docs/guides/tools-file-search
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(".env", override=True)

from openai import OpenAI
client = OpenAI()

# Get vector store ID from environment
VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID")
FILES_DIR = "data/files"

print(f"Vector Store ID: {VECTOR_STORE_ID}\n")

# List existing files in vector store
print("=== Existing files in vector store ===")
existing_files = client.vector_stores.files.list(vector_store_id=VECTOR_STORE_ID)
existing_filenames = set()

for file_obj in existing_files.data:
    # Get file details
    file_details = client.files.retrieve(file_obj.id)
    print(f"- {file_details.filename} (ID: {file_obj.id}, Status: {file_obj.status})")
    existing_filenames.add(file_details.filename)

print(f"\nTotal files in vector store: {len(existing_filenames)}\n")

# Get all files from data/files directory
print("=== Files in data/files directory ===")
files_to_upload = []
for file_path in Path(FILES_DIR).glob("*"):
    if file_path.is_file() and file_path.name != ".keep":
        print(f"- {file_path.name}")
        if file_path.name not in existing_filenames:
            files_to_upload.append(file_path)

print(f"\nTotal files in directory: {len(list(Path(FILES_DIR).glob('*'))) - 1}\n")  # -1 for .keep

# Upload new files
if files_to_upload:
    print(f"=== Uploading {len(files_to_upload)} new files ===")
    for file_path in files_to_upload:
        print(f"Uploading {file_path.name}...", end=" ")
        try:
            result = client.vector_stores.files.upload(
                vector_store_id=VECTOR_STORE_ID,
                file=open(file_path, "rb")
            )
            print(f"✓ Success (Status: {result.status})")
        except Exception as e:
            print(f"✗ Failed: {e}")
    print("\n=== Upload complete ===")
else:
    print("=== No new files to upload ===")
    print("All files in data/files are already in the vector store.")