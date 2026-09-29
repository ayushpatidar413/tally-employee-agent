import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# RESEARCH LLM
# ============================================================

research_llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY"),
)


# ============================================================
# RESEARCH AGENT
# ============================================================

def research_agent(query: str):
    """
    General Research Agent.

    Handles general knowledge and research questions
    that are not specific to the uploaded dataset or
    employee HR database.
    """

    query = (query or "").strip()

    if not query:

        return {
            "success": False,
            "message": "Please enter a question.",
            "data": {},
        }

    # ========================================================
    # RESEARCH SYSTEM INSTRUCTION
    # ========================================================

    system_prompt = """
You are the Research Agent of a multi-agent AI system.

Your responsibility is to answer general knowledge,
educational, conceptual, and research questions.

Examples:

- What is AI?
- What is machine learning?
- Explain LangChain.
- What is employee onboarding?
- What is recruitment?
- What is performance appraisal?
- What is a database?
- Explain cloud computing.

IMPORTANT RULES:

1. Answer the user's question directly.

2. Give clear and understandable explanations.

3. Do not pretend that you accessed an uploaded file.

4. Do not invent employee records, salaries,
   attendance, PF, leave, or other company-specific
   information.

5. If the question asks about a specific employee,
   uploaded dataset, uploaded file, or company record,
   that information should be handled by the appropriate
   HR/Data Agent instead.

6. Do not say that information is unavailable in the
   uploaded file unless the question is actually about
   uploaded data.

7. Keep the answer concise but useful.

8. Use examples when they help understanding.
"""

    # ========================================================
    # BUILD MESSAGE
    # ========================================================

    prompt = f"""
{system_prompt}

User Question:
{query}
"""

    # ========================================================
    # CALL GROQ
    # ========================================================

    try:

        response = research_llm.invoke(
            prompt
        )

        answer = response.content

        if not answer:

            return {
                "success": False,
                "message": (
                    "I could not generate a research answer."
                ),
                "data": {},
            }

        return {
            "success": True,
            "message": str(answer),
            "data": {
                "topic": "General Research",
                "query": query,
            },
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                "I could not generate a research answer."
            ),
            "data": {
                "error": str(error),
            },
        }