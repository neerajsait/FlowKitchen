from app import create_app
from models import db, Category
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Starting category migration...")
    db.create_all()
    
    try:
        res = db.session.execute(text("SHOW COLUMNS FROM menu_items LIKE 'category'")).fetchone()
        has_category_col = res is not None
    except Exception as e:
        print(f"Error checking column: {e}")
        has_category_col = False

    try:
        db.session.execute(text("ALTER TABLE menu_items ADD COLUMN category_id INTEGER"))
        db.session.execute(text("ALTER TABLE menu_items ADD CONSTRAINT fk_menu_items_category_id FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL"))
        print("Added category_id column and foreign key constraint.")
    except Exception as e:
        print("Note: category_id column or FK might already exist.")

    uncategorized = Category.query.filter_by(name="Uncategorized").first()
    if not uncategorized:
        uncategorized = Category(name="Uncategorized")
        db.session.add(uncategorized)
        db.session.commit()
        print("Created Uncategorized category.")

    if has_category_col:
        categories_data = db.session.execute(text("SELECT DISTINCT category FROM menu_items WHERE category IS NOT NULL AND category != ''")).fetchall()
        for row in categories_data:
            cat_name = row[0].strip()
            # Case insensitive check
            cat = Category.query.filter(Category.name.ilike(cat_name)).first()
            if not cat:
                cat = Category(name=cat_name)
                db.session.add(cat)
        db.session.commit()
        print("Migrated existing string categories to Category table.")

        all_cats = Category.query.all()
        for cat in all_cats:
            # We use LOWER for case-insensitive matching across collations just in case
            db.session.execute(
                text("UPDATE menu_items SET category_id = :cat_id WHERE LOWER(category) = LOWER(:cat_name)"),
                {"cat_id": cat.id, "cat_name": cat.name}
            )
        db.session.commit()
        print("Updated menu_items with category_id.")

        try:
            db.session.execute(text("ALTER TABLE menu_items DROP COLUMN category"))
            db.session.commit()
            print("Dropped old category column.")
        except Exception as e:
            print("Failed to drop category column:", e)
    else:
        print("Old category column not found. Migration likely already ran.")
    
    print("Migration complete!")
