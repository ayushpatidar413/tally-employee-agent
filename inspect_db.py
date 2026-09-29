import sqlite3

con = sqlite3.connect("database/dynamic_data.db")
cur = con.cursor()

cur.execute("""
SELECT name
FROM sqlite_master
WHERE type = 'table'
""")

print("TABLES:")
for row in cur.fetchall():
    print(row[0])

con.close()
