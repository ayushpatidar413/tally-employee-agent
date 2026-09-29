import re


# ============================================================
# HR QUERY PATTERNS
# ============================================================

HR_PATTERNS = [
    r"\bemp\d+\b",
    r"\bemp[-_ ]?\d+\b",
    r"\bemployee\s+id\b",
    r"\bemployee\s+code\b",
    r"\bspecific employee\b",
    r"\bspecific employee's\b",
    r"\battendance\b",
    r"\battendances\b",
    r"\bpf\b",
    r"\bprovident fund\b",
    r"\bpayroll\b",
    r"\bnet salary\b",
    r"\bgross salary\b",
    r"\bleave balance\b",
    r"\bleave record\b",
    r"\bleave records\b",
]


# ============================================================
# DYNAMIC DATA QUERY KEYWORDS
# ============================================================

GENERIC_DATA_KEYWORDS = [
    "uploaded file",
    "uploaded data",
    "uploaded document",
    "uploaded dataset",
    "dataset",
    "data",
    "records",
    "rows",
    "columns",
    "fields",
    "total",
    "sum",
    "average",
    "avg",
    "mean",
    "minimum",
    "maximum",
    "highest",
    "lowest",
    "count",
    "show",
    "find",
    "filter",
    "where",
    "containing",
    "contains",
    "equal to",
    "greater than",
    "less than",
    "group by",
    "grouped by",
    "by category",
    "by department",
    "by month",
    "by date",
    "sort",
    "sorted",
    "top",
    "bottom",
]


# ============================================================
# RESEARCH QUERY KEYWORDS
# ============================================================

RESEARCH_KEYWORDS = [
    "what is",
    "what are",
    "explain",
    "define",
    "definition",
    "meaning of",
    "how does",
    "how do",
    "why",
    "process",
    "concept",
    "policy",
    "policies",
    "onboarding",
    "recruitment",
    "hiring",
    "performance appraisal",
    "performance review",
    "retention",
    "hr policy",
    "hr policies",
]


# ============================================================
# NORMALIZE QUERY
# ============================================================

def normalize_query(query: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(query).strip().lower(),
    )


# ============================================================
# HR QUERY
# ============================================================

def is_hr_query(query: str) -> bool:
    normalized_query = normalize_query(query)

    for pattern in HR_PATTERNS:
        if re.search(pattern, normalized_query):
            return True

    return False


# ============================================================
# DYNAMIC DATA QUERY
# ============================================================

def is_generic_data_query(query: str) -> bool:
    normalized_query = normalize_query(query)

    for keyword in GENERIC_DATA_KEYWORDS:
        if keyword in normalized_query:
            return True

    return False


# ============================================================
# RESEARCH QUERY
# ============================================================

def is_research_query(query: str) -> bool:
    normalized_query = normalize_query(query)

    for keyword in RESEARCH_KEYWORDS:
        if keyword in normalized_query:
            return True

    return False


# ============================================================
# MAIN ROUTER
# ============================================================

def route_query(query: str) -> str:
    normalized_query = normalize_query(query)

    # --------------------------------------------------------
    # 1. Specific employee / HR database questions
    # --------------------------------------------------------

    if is_hr_query(normalized_query):
        return "hr"

    # --------------------------------------------------------
    # 2. Uploaded-file / dataset questions
    # --------------------------------------------------------

    if is_generic_data_query(normalized_query):
        return "dynamic"

    # --------------------------------------------------------
    # 3. General knowledge / research questions
    # --------------------------------------------------------

    if is_research_query(normalized_query):
        return "research"

    # --------------------------------------------------------
    # 4. Default
    # --------------------------------------------------------

    return "research"