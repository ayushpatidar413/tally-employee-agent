from services.dynamic_upload_service import process_uploaded_file
from database.dynamic_data_db import get_dataset_rows


result = process_uploaded_file(
    file_path="test_rows.csv",
    original_filename="test_rows.csv",
    stored_filename="test_rows.csv",
)


print()
print("SUCCESS:", result["success"])
print("DATASET ID:", result["dataset"]["id"])
print("DATASET TYPE:", result["dataset"]["data_type"])
print("ROWS SAVED:", result["rows_saved"])


dataset_id = result["dataset"]["id"]

rows = get_dataset_rows(
    dataset_id
)


print()
print("DATABASE ROW COUNT:", len(rows))

print()

for row in rows:
    print(
        row["row_number"],
        row["data"]
    )