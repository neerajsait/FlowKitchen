import traceback
from app import create_app, db
from models import Staff
from flask_bcrypt import Bcrypt

app = create_app()
bcrypt = Bcrypt(app)

with app.app_context():
    try:
        user = Staff(
            email="test123123@foodpilot.local",
            full_name="Test Staff",
            phone="1234567890",
            outlet_id=1
        )
        user.set_password("Password123!", bcrypt)
        user.set_pin("1234", bcrypt)
        user.staff_code = "1234"
        
        db.session.add(user)
        db.session.commit()
        print("Success!")
    except Exception as e:
        print("Error occurred:")
        traceback.print_exc()
