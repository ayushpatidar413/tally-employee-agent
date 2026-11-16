"""intent_engine - one canonical path:  Ground -> Plan(LLM, typed) -> Validate/Repair -> Execute(code) -> Explain.

The LLM only produces a PLAN. Dates, entity values and metric columns are resolved by code and handed to the
LLM as facts, and a validator rejects any plan that drops something the user said.  Numbers come from pandas only.
"""
from .pipeline import run, IntentResult            # noqa: F401
from .grounding import DatasetCard, ground          # noqa: F401
