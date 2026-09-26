import pymysql
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')

host = os.getenv('MYSQL_HOST', 'localhost')
user = os.getenv('MYSQL_USER', 'root')
password = os.getenv('MYSQL_PASSWORD', 'root')
db = os.getenv('MYSQL_DB', 'food')

conn = pymysql.connect(host=host, user=user, password=password, database=db)
cursor = conn.cursor()

try:
    cursor.execute("SHOW COLUMNS FROM users LIKE 'full_name'")
    if not cursor.fetchone():
        print("Adding full_name column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN full_name VARCHAR(100) NULL")
        
        print("Migrating data...")
        cursor.execute("UPDATE users SET full_name = TRIM(CONCAT(COALESCE(first_name, ''), ' ', COALESCE(last_name, '')))")
        
        print("Dropping old columns...")
        cursor.execute("ALTER TABLE users DROP COLUMN first_name, DROP COLUMN last_name")
        
        conn.commit()
        print("Migration successful.")
    else:
        print("Migration already applied.")
except Exception as e:
    print("Error:", e)
    conn.rollback()
finally:
    conn.close()
