import sqlite3
conn = sqlite3.connect("dev.db")
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("Tables:", tables)
conn.close()
