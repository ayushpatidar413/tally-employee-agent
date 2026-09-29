from agents.hr_tools import HR_TOOLS


print("=" * 70)
print("LANGCHAIN HR TOOLS")
print("=" * 70)

print("\nTotal tools:", len(HR_TOOLS))

print("\nAvailable tools:")

for tool in HR_TOOLS:
    print(
        f"- {tool.name}"
    )

print("\n" + "=" * 70)
print("TOOLS LOADED SUCCESSFULLY")
print("=" * 70)