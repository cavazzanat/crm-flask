# init_db.py
import sqlite3

with open("models.sql", "r", encoding="utf-8") as f:
    sql_script = f.read()

conn = sqlite3.connect("crm.db")
cursor = conn.cursor()
cursor.executescript(sql_script)
conn.commit()
conn.close()

print("✅ Base de données initialisée")