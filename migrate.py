import sqlite3

def migrate_db():
    conn = sqlite3.connect('backend/instance/food.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('PRAGMA table_info(users)')
        columns = [col[1] for col in cursor.fetchall()]
        if 'full_name' not in columns:
            print('Adding full_name column...')
            cursor.execute('ALTER TABLE users ADD COLUMN full_name VARCHAR(100)')
            
            print('Migrating data...')
            cursor.execute("UPDATE users SET full_name = coalesce(first_name, '') || ' ' || coalesce(last_name, '')")
            cursor.execute("UPDATE users SET full_name = trim(full_name)")
            
            print('Dropping old columns...')
            try:
                cursor.execute('ALTER TABLE users DROP COLUMN first_name')
                cursor.execute('ALTER TABLE users DROP COLUMN last_name')
            except sqlite3.OperationalError:
                print("SQLite version doesn't support DROP COLUMN, ignoring...")
            
            conn.commit()
            print('Migration successful.')
        else:
            print('Migration already applied.')
    except Exception as e:
        print('Error:', e)
        conn.rollback()
    finally:
        conn.close()

migrate_db()
