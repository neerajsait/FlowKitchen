from flask import Flask
from flask_bcrypt import Bcrypt
import sqlite3

app = Flask(__name__)
bcrypt = Bcrypt(app)

with app.app_context():
    pwd = bcrypt.generate_password_hash("admin123").decode('utf-8')
    conn = sqlite3.connect('instance/food.db')
    conn.execute('UPDATE users SET password_hash = ? WHERE email = \'admin\'', (pwd,))
    conn.execute('UPDATE users SET is_first_login = 1 WHERE email = \'admin\'')
    conn.commit()
    conn.close()
    print("Admin password securely reset to admin123 using Flask-Bcrypt")
