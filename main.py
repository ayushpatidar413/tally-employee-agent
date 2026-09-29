
from graph.workflow import hr_graph

from database.history_db import (
    create_history_table,
    save_chat_history,
)


def main():

    # ============================================================
    # CREATE HISTORY DATABASE
    # ============================================================

    create_history_table()

    print("=" * 70)
    print("TALLY EMPLOYEE HR AGENT")
    print("=" * 70)
    print("Type your HR question.")
    print("Type 'exit' to stop.")
    print()

    while True:

        user_query = input("You: ").strip()

        # ========================================================
        # EXIT
        # ========================================================

        if user_query.lower() in {"exit", "quit"}:
            print("\nHR Agent stopped.")
            break

        # ========================================================
        # EMPTY QUESTION
        # ========================================================

        if not user_query:
            print("Please enter a question.")
            continue

        try:

            # ====================================================
            # RUN LANGGRAPH
            # ====================================================

            result = hr_graph.invoke(
                {
                    "user_query": user_query
                }
            )

            print("\n" + "-" * 70)
            print("HR AGENT:")
            print("-" * 70)

            answer = result.get("final_answer")

            if answer:

                print(answer)

                # ================================================
                # SAVE QUESTION + ANSWER TO HISTORY
                # ================================================

                try:

                    save_chat_history(
                        user_query=user_query,
                        answer=answer,
                        intent=result.get("intent"),
                        employee_name=result.get("employee_name"),
                        employee_id=result.get("employee_id"),
                    )

                    print("\n[Conversation saved to history]")

                except Exception as history_error:

                    print(
                        "\n[Warning: Could not save conversation "
                        f"to history: {history_error}]"
                    )

            else:

                print("No answer was generated.")

            print("-" * 70)
            print()

        except Exception as e:

            print("\nERROR:")
            print(str(e))
            print()


if __name__ == "__main__":
    main()

