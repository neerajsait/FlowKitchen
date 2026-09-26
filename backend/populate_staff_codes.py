import os
from dotenv import load_dotenv
import random
from sqlalchemy import select

# Load environment before anything else
load_dotenv()

# We only need the app context
from app import create_app, db
from models import User

def populate_staff_codes():
    app = create_app()
    with app.app_context():
        # Get all staff/kitchen who lack a staff_code
        users = db.session.scalars(
            select(User).where(User.role.in_(['staff', 'kitchen']), User.staff_code.is_(None))
        ).all()
        
        if not users:
            print("All staff/kitchen users already have a staff_code.")
            return

        updated = 0
        for user in users:
            # Generate a unique 4-digit code
            while True:
                code = str(random.randint(1000, 9999))
                # Check uniqueness
                if not db.session.scalars(select(User).where(User.staff_code == code)).first():
                    user.staff_code = code
                    updated += 1
                    break
        
        db.session.commit()
        print(f"Successfully populated staff_code for {updated} users.")

if __name__ == "__main__":
    populate_staff_codes()
