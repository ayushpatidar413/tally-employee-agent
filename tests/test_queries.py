from graph.workflow import hr_graph


TEST_CASES = [
    {
        "name": "Summary",
        "query": "Give me complete details of EMP001",
        "expected_intent": "summary",
    },
    {
        "name": "Salary",
        "query": "What is the salary of EMP001?",
        "expected_intent": "salary",
        "expected_value": "48000",
    },
    {
        "name": "Attendance",
        "query": "What is the attendance of EMP001?",
        "expected_intent": "attendance",
        "expected_value": "78",
    },
    {
        "name": "Leave",
        "query": "How many leaves did EMP001 take?",
        "expected_intent": "leave",
        "expected_value": "0",
    },
    {
        "name": "PF",
        "query": "What is the PF of EMP001?",
        "expected_intent": "pf",
        "expected_value": "5760",
    },
    {
        "name": "Experience",
        "query": "What is the experience of Rajesh Sharma?",
        "expected_intent": "experience",
        "expected_value": "5.5",
    },
    {
        "name": "Complete Details",
        "query": "Give me all information about Rajesh Sharma",
        "expected_intent": "summary",
    },
]


def run_test(test_case):

    print("\n" + "=" * 70)
    print(f"TEST: {test_case['name']}")
    print("=" * 70)

    print(f"Query: {test_case['query']}")

    try:

        result = hr_graph.invoke(
            {
                "user_query": test_case["query"]
            }
        )

        intent = result.get("intent")
        employee_id = result.get("employee_id")
        employee_name = result.get("employee_name")
        final_answer = result.get("final_answer", "")

        print(f"\nDetected Intent : {intent}")
        print(f"Employee ID     : {employee_id}")
        print(f"Employee Name   : {employee_name}")

        print("\nFinal Answer:")
        print(final_answer)

        test_passed = True

        # ---------------------------------------------------------
        # INTENT CHECK
        # ---------------------------------------------------------

        expected_intent = test_case.get("expected_intent")

        if expected_intent:

            if intent == expected_intent:

                print(
                    f"\nIntent check: PASS ({expected_intent})"
                )

            else:

                print(
                    f"\nIntent check: FAIL"
                )

                print(
                    f"Expected: {expected_intent}"
                )

                print(
                    f"Actual:   {intent}"
                )

                test_passed = False

        # ---------------------------------------------------------
        # EXPECTED VALUE CHECK
        # ---------------------------------------------------------

        expected_value = test_case.get(
            "expected_value"
        )

        if expected_value:

            # Remove common formatting characters.
            #
            # Example:
            # 48,000.00 -> 48000.00
            # ₹5,760.00 -> 5760.00

            normalized_answer = (
                str(final_answer)
                .replace(",", "")
                .replace("₹", "")
                .replace(" ", "")
            )

            normalized_expected = (
                str(expected_value)
                .replace(",", "")
                .replace("₹", "")
                .replace(" ", "")
            )

            if normalized_expected in normalized_answer:

                print(
                    f"Expected value check: PASS ({expected_value})"
                )

            else:

                print(
                    "Expected value check: FAIL"
                )

                print(
                    f"Expected value: {expected_value}"
                )

                test_passed = False

        # ---------------------------------------------------------
        # EMPLOYEE CHECK
        # ---------------------------------------------------------

        if "EMP001" in test_case["query"]:

            if employee_id == "EMP001":

                print(
                    "Employee check: PASS (EMP001)"
                )

            else:

                print(
                    "Employee check: FAIL"
                )

                print(
                    f"Expected employee ID: EMP001"
                )

                print(
                    f"Actual employee ID: {employee_id}"
                )

                test_passed = False

        # ---------------------------------------------------------
        # NAME CHECK
        # ---------------------------------------------------------

        if "Rajesh Sharma" in test_case["query"]:

            if employee_name == "Rajesh Sharma":

                print(
                    "Employee name check: PASS (Rajesh Sharma)"
                )

            else:

                print(
                    "Employee name check: FAIL"
                )

                print(
                    f"Expected name: Rajesh Sharma"
                )

                print(
                    f"Actual name: {employee_name}"
                )

                test_passed = False

        # ---------------------------------------------------------
        # FINAL RESULT
        # ---------------------------------------------------------

        if test_passed:

            print("\nRESULT: PASS")
            return True

        else:

            print("\nRESULT: FAIL")
            return False

    except Exception as error:

        print("\nRESULT: ERROR")

        print(
            f"Error: {error}"
        )

        return False


def main():

    print("\n" + "=" * 70)
    print("HR QUERY TEST SUITE")
    print("=" * 70)

    passed = 0
    failed = 0

    for test_case in TEST_CASES:

        result = run_test(test_case)

        if result:

            passed += 1

        else:

            failed += 1

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    print(f"Total Tests : {len(TEST_CASES)}")
    print(f"Passed      : {passed}")
    print(f"Failed      : {failed}")

    if failed == 0:

        print("\nALL TESTS PASSED!")

    else:

        print(
            f"\n{failed} TEST(S) FAILED."
        )

    print("=" * 70)


if __name__ == "__main__":
    main()