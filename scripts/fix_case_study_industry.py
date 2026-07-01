import sqlite3

conn = sqlite3.connect("ken_links.db")
cursor = conn.execute("UPDATE content_nodes SET industry = '' WHERE industry = 'Case Studies'")
conn.commit()
print(f"Cleared {cursor.rowcount} rows with wrong 'Case Studies' industry")
conn.close()
