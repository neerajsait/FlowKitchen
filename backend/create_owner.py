from app import create_app, db, bcrypt
from models import OutletOwner, Outlet

app = create_app()

with app.app_context():
    outlet = Outlet.query.first()
    if not outlet:
        print("No outlet found!")
    else:
        owner = OutletOwner.query.filter_by(email="owner@example.com").first()
        if not owner:
            owner = OutletOwner(email="owner@example.com", full_name="Outlet Owner", outlet_id=outlet.id)
            owner.set_password("password", bcrypt)
            db.session.add(owner)
            db.session.commit()
            print("Outlet Owner created!")
        else:
            owner.outlet_id = outlet.id
            owner.set_password("password", bcrypt)
            db.session.commit()
            print("Outlet Owner updated!")
