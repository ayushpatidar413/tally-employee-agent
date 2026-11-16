import unittest

from services.vyapar_master_prompt import (
    VYAPAR_MASTER_SYSTEM_PROMPT,
    attach_vyapar_master_policy,
)


class VyaparMasterPromptTests(unittest.TestCase):
    def test_policy_contains_core_reliability_rules(self):
        policy = VYAPAR_MASTER_SYSTEM_PROMPT.lower()
        for phrase in (
            "never invent a column",
            "never add a product",
            "actual dates",
            "preserve every requested metric",
            "aggregate at the requested grouping level",
            "never calculate numeric answers",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, policy)

    def test_policy_is_appended_to_existing_prompt(self):
        existing = "EXISTING JSON SCHEMA\nReturn JSON only."
        combined = attach_vyapar_master_policy(existing)
        self.assertIn(existing, combined)
        self.assertIn(VYAPAR_MASTER_SYSTEM_PROMPT, combined)
        self.assertTrue(combined.endswith(VYAPAR_MASTER_SYSTEM_PROMPT))

    def test_policy_is_not_duplicated(self):
        once = attach_vyapar_master_policy("Existing prompt")
        twice = attach_vyapar_master_policy(once)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count(VYAPAR_MASTER_SYSTEM_PROMPT), 1)

    def test_empty_prompt_returns_policy(self):
        self.assertEqual(
            attach_vyapar_master_policy("  "),
            VYAPAR_MASTER_SYSTEM_PROMPT,
        )


if __name__ == "__main__":
    unittest.main()
