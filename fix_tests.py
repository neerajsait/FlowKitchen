import os
import re

test_dir = r"d:\python project\food\backend\tests"

files_to_fix = [
    "test_admin.py",
    "test_customer.py",
    "test_kitchen.py",
    "test_owner_analytics.py",
    "test_pos.py",
    "test_pos_orders.py"
]

for filename in files_to_fix:
    path = os.path.join(test_dir, filename)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 1. Import Category
    if "Category" not in content:
        content = re.sub(r'from models import (.*)', r'from models import \1, Category', content)
    
    # 2. Add Category to setUp
    setup_addition = '''        db.create_all()
        
        self.category = Category(name="Main")
        db.session.add(self.category)
        db.session.commit()'''
    content = content.replace("        db.create_all()", setup_addition)
    
    # 3. Replace MenuItem category="X" with category_id=self.category.id
    content = re.sub(r'category="[^"]*"', r'category_id=self.category.id', content)
    
    # 4. Replace API payload "category": "X" with "category_id": self.category.id
    # Note: test_admin.py has "category": "Main" inside JSON, which should be "category_id": self.category.id
    # Let's replace '"category": "[^"]*"' with '"category_id": self.category.id' (Wait, in JSON it shouldn't be self.category.id stringified, it needs to evaluate to the integer).
    # Since it's inside a json dict:
    content = re.sub(r'"category":\s*"[^"]*"', r'"category_id": self.category.id', content)
    content = re.sub(r"'category':\s*'[^']*'", r"'category_id': self.category.id", content)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

print("Tests updated.")
