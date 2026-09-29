from models import create_tables


if __name__ == "__main__":

    print("=" * 70)
    print("INITIALIZING HR PAYROLL DATABASE")
    print("=" * 70)

    create_tables()

    print("\nDatabase initialization completed.")