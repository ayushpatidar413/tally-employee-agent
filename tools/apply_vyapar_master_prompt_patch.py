from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "graph" / "dynamic_nodes.py"
IMPORT_LINE = "from services.vyapar_master_prompt import attach_vyapar_master_policy"
ANCHOR = "    # EXISTING LLM PATH\n"
INJECT = (
    "    # Shared master policy is applied only when the LLM planner path is used.\n"
    "    # Deterministic fast paths continue to use their existing validated logic.\n"
    "    prompt = attach_vyapar_master_policy(prompt)\n\n"
)

def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"ERROR: {TARGET} not found. Run this script from the extracted project root.")
    source = TARGET.read_text(encoding="utf-8-sig")

    if IMPORT_LINE in source and "prompt = attach_vyapar_master_policy(prompt)" in source:
        print("Patch already applied; no changes made.")
        return

    if source.count(ANCHOR) != 1:
        raise SystemExit(
            f"ERROR: expected exactly one {ANCHOR.strip()!r} anchor, "
            f"found {source.count(ANCHOR)}. No files changed."
        )

    backup = TARGET.with_name(
        f"{TARGET.name}.before_master_prompt_{datetime.now():%Y%m%d_%H%M%S}.bak"
    )
    shutil.copy2(TARGET, backup)

    # Add import near the existing query spellcheck import.
    spellcheck_import = "from services.query_spellcheck import correct_query_typos"
    if spellcheck_import not in source:
        raise SystemExit("ERROR: expected query spellcheck import not found. No files changed.")
    source = source.replace(
        spellcheck_import,
        spellcheck_import + "\n" + IMPORT_LINE,
        1,
    )

    # Add the policy immediately before the existing LLM invocation path.
    source = source.replace(ANCHOR, INJECT + ANCHOR, 1)

    # Syntax-check before writing.
    ast.parse(source, filename=str(TARGET))
    TARGET.write_text(source, encoding="utf-8")
    print("Master prompt integration applied.")
    print(f"Backup: {backup}")
    print("Integrated runtime call site: graph.dynamic_nodes.universal_query_planner")
    print("Gemini and Groq receive the same combined prompt.")
    print("Deterministic fast paths remain unchanged.")

if __name__ == "__main__":
    main()
