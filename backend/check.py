import sqlite3; conn = sqlite3.connect('food.db'); c = conn.cursor(); c.execute('SELECT id, email, role, staff_code, pin_hash FROM users'); print(c.fetchall())
