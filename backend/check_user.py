from app import create_app, db, bcrypt
from models import Staff, Outlet

app = create_app()

with app.app_context():
    outlet = Outlet.query.first()
    if not outlet:
        print("No outlet found!")
    else:
        # Create staff 2522
        staff = Staff.query.get(2522)
        if not staff:
            staff = Staff(email="staff_2522_new@example.com", full_name="Demo Staff", outlet_id=outlet.id)
            staff.id = 2522
            staff.password_hash = bcrypt.generate_password_hash("dummy").decode('utf-8')
            staff.set_pin("1234", bcrypt)
            db.session.add(staff)
            db.session.commit()
            print("Staff 2522 created and assigned to outlet!")
        else:
            staff.outlet_id = outlet.id
            staff.set_pin("1234", bcrypt)
            db.session.commit()
            print("Staff 2522 updated and assigned to outlet!")
