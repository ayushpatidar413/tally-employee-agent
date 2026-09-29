from pathlib import Path

from tools.dynamic_file_loader import (
    process_uploaded_file
)


class DynamicHRAgent:
    """
    Dynamic HR Agent

    Responsibilities:
    1. Receive uploaded HR/Tally file.
    2. Detect file type.
    3. Validate the data.
    4. Store data in SQLite.
    5. Return processing result.
    """

    def __init__(self):

        self.name = "Dynamic HR Data Agent"

    def process_file(
        self,
        file_path
    ):

        file_path = Path(file_path)

        if not file_path.exists():

            return {
                "success": False,
                "message": (
                    f"File not found: "
                    f"{file_path}"
                )
            }

        print(
            f"\n{self.name}"
        )

        print(
            f"Processing: "
            f"{file_path.name}"
        )

        result = process_uploaded_file(
            file_path
        )

        return result


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print(
            "Usage:"
        )

        print(
            "python agents/dynamic_hr_agent.py "
            "file.csv"
        )

        sys.exit()

    agent = DynamicHRAgent()

    result = agent.process_file(
        sys.argv[1]
    )

    print("\n" + "=" * 70)
    print("DYNAMIC HR AGENT RESULT")
    print("=" * 70)

    for key, value in result.items():

        print(
            f"{key}: {value}"
        )