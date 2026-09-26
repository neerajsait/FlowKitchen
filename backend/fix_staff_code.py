from app import create_app, db
from models import Staff

app = create_app()

with app.app_context():
    staff = Staff.query.get(2522)
    if staff:
        staff.staff_code = "2522"
        db.session.commit()
        print("Updated staff_code for user 2522!")
    else:
        print("Staff not found.")
