from pathlib import Path
from typing import Any

from database.dynamic_data_db import (
    get_dataset,
    get_datasets,
    get_latest_dataset,
    delete_dataset as delete_dataset_metadata,
)

from services.dynamic_data_service import (
    load_structured_data,
)


# ============================================================
# LOAD DATASET BY ID
# ============================================================

def load_dataset_by_id(
    dataset_id: int,
) -> dict[str, Any]:
    """
    Find a dataset from dynamic_data.db and load its
    original physical file into a Pandas DataFrame.

    NOTE:
    The Universal Data Agent should prefer persisted SQLite
    rows for querying. This function is mainly useful when
    the physical uploaded file is still available.
    """

    dataset = get_dataset(dataset_id)

    if not dataset:
        return {
            "success": False,
            "message": "The uploaded dataset could not be found.",
        }

    if dataset.get("status") != "SUCCESS":
        return {
            "success": False,
            "message": "The uploaded dataset is not available.",
        }

    file_path = dataset.get("file_path")

    if not file_path:
        return {
            "success": False,
            "message": "The uploaded dataset file is not available.",
        }

    path = Path(file_path)

    if not path.exists():
        return {
            "success": False,
            "message": (
                "The original uploaded file is no longer available. "
                "Persisted dataset data may still exist in SQLite."
            ),
        }

    try:

        dataframe = load_structured_data(path)

        return {
            "success": True,
            "dataset": dataset,
            "dataframe": dataframe,
        }

    except Exception as error:

        return {
            "success": False,
            "message": "Unable to read the uploaded dataset.",
            "error": str(error),
        }


# ============================================================
# LOAD LATEST DATASET
# ============================================================

def load_latest_uploaded_dataset() -> dict[str, Any]:
    """
    Load the most recently uploaded successful dataset.
    """

    dataset = get_latest_dataset()

    if not dataset:
        return {
            "success": False,
            "message": "No uploaded dataset is available.",
        }

    return load_dataset_by_id(dataset["id"])


# ============================================================
# GET LATEST DATASET INFORMATION
# ============================================================

def get_latest_dataset_info() -> dict[str, Any]:
    """
    Return metadata about the latest uploaded dataset
    without loading the complete DataFrame.
    """

    dataset = get_latest_dataset()

    if not dataset:
        return {
            "success": False,
            "message": "No uploaded dataset is available.",
        }

    return {
        "success": True,
        "dataset": dataset,
    }


# ============================================================
# GET ALL DATASETS
# ============================================================

def get_all_uploaded_datasets() -> dict[str, Any]:
    """
    Return all datasets stored in dynamic_data.db.
    """

    datasets = get_datasets()

    return {
        "success": True,
        "count": len(datasets),
        "datasets": datasets,
    }


# ============================================================
# GET DATASET BY ID
# ============================================================

def get_uploaded_dataset(
    dataset_id: int,
) -> dict[str, Any]:
    """
    Return metadata for one dataset.
    """

    dataset = get_dataset(dataset_id)

    if not dataset:
        return {
            "success": False,
            "message": "Dataset not found.",
        }

    return {
        "success": True,
        "dataset": dataset,
    }


# ============================================================
# DELETE DATASET
# ============================================================

def delete_uploaded_dataset(
    dataset_id: int,
) -> dict[str, Any]:
    """
    Delete a dataset from the dynamic database.

    IMPORTANT:
    The SQLite database is the persistent source of truth.

    The physical uploaded file is NOT required for querying
    the persisted dataset.

    Therefore this function removes the dataset metadata,
    schema and persisted rows from SQLite, but does not
    depend on deleting the physical file.

    This also prevents a physical-file deletion from being
    confused with a database deletion.
    """

    dataset = get_dataset(dataset_id)

    if not dataset:

        return {
            "success": False,
            "message": "Dataset not found.",
        }

    # --------------------------------------------------------
    # DELETE DATASET FROM SQLITE
    # --------------------------------------------------------

    deleted = delete_dataset_metadata(
        dataset_id
    )

    # delete_dataset() returns a boolean.
    if not deleted:

        return {
            "success": False,
            "message": "Unable to delete dataset metadata.",
            "dataset_id": dataset_id,
        }

    # --------------------------------------------------------
    # IMPORTANT
    # --------------------------------------------------------
    #
    # We intentionally DO NOT delete the physical file here.
    #
    # SQLite is our persistent source of truth.
    #
    # If the physical file is removed independently,
    # persisted data remains available in SQLite.
    #
    # --------------------------------------------------------

    return {
        "success": True,
        "dataset_id": dataset_id,
        "original_filename": dataset.get(
            "original_filename"
        ),
        "stored_filename": dataset.get(
            "stored_filename"
        ),
        "file_path": dataset.get(
            "file_path"
        ),
        "file_deleted": False,
        "metadata_deleted": True,
        "message": (
            "Dataset metadata and persisted rows "
            "were deleted successfully."
        ),
    }


# ============================================================
# CHECK DATASET AVAILABILITY
# ============================================================

def has_uploaded_dataset() -> bool:
    """
    Check whether at least one dataset exists.
    """

    dataset = get_latest_dataset()

    return dataset is not None


# ============================================================
# DATASET SUMMARY
# ============================================================

def get_latest_dataset_summary() -> dict[str, Any]:
    """
    Return a small summary of the latest dataset.
    """

    result = load_latest_uploaded_dataset()

    if not result.get("success"):
        return result

    dataset = result["dataset"]
    dataframe = result["dataframe"]

    return {
        "success": True,
        "dataset_id": dataset["id"],
        "filename": dataset["original_filename"],
        "file_type": dataset["file_type"],
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
        "columns": [
            str(column)
            for column in dataframe.columns
        ],
    }