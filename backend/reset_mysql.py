from app import create_app
from models import db, User
from flask_bcrypt import Bcrypt

app = create_app()
bcrypt = Bcrypt(app)

with app.app_context():
    admin = db.session.scalars(db.select(User).where(User.email == 'admin')).first()
    if admin:
        admin.password_hash = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin.is_first_login = True
        db.session.commit()
        print("Admin password securely reset to admin123 in MySQL database.")
    else:
        print("Admin user not found!")
