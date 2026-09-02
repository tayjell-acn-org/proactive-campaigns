import sqlite3

conn = sqlite3.connect("campaign.db")

cursor = conn.cursor()

cursor.execute("""
    SELECT *
    FROM AccountContactHistory
""")

rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()