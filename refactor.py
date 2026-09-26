import os
import re

def process_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replacing first_name and last_name in arguments, variables
    content = re.sub(r'first_name=first_name, last_name=last_name', 'full_name=full_name', content)
    content = re.sub(r'first_name=first_name or None, last_name=last_name or None', 'full_name=full_name or None', content)
    content = re.sub(r'first_name=None, last_name=None', 'full_name=None', content)
    content = re.sub(r'self\.first_name = first_name', 'self.full_name = full_name', content)
    
    # Models definitions
    content = re.sub(r'first_name = Column\(String\(50\), nullable=True\)', 'full_name = Column(String(100), nullable=True)', content)
    content = re.sub(r'\s*last_name = Column\(String\(50\), nullable=True\)', '', content)
    
    # Dictionaries/JSON serialization
    content = re.sub(r'\"first_name\": self\.first_name,', '\"full_name\": self.full_name,', content)
    content = re.sub(r'\s*\"last_name\": self\.last_name,', '', content)

    # String format replacements
    # f"{self.customer.first_name or ''} {self.customer.last_name or ''}".strip() 
    # to self.customer.full_name
    content = re.sub(r'f\"\{([^\}]*)\.first_name or \'\'\} \{([^\}]*)\.last_name or \'\'\}\"\.strip\(\)', r'\1.full_name', content)
    content = re.sub(r'f\"\{([^\}]*)\.first_name\} \{([^\}]*)\.last_name\}\"', r'\1.full_name', content)

    # For other properties and methods (e.g. self.first_name -> self.full_name)
    content = re.sub(r'\.first_name', '.full_name', content)
    
    # Some hardcoded test data replacements
    content = re.sub(r'first_name="([^"]+)", last_name="([^"]+)"', r'full_name="\1 \2"', content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

files_to_process = [
    'backend/models.py',
    'backend/app.py',
    'backend/admin.py',
    'backend/check_user.py',
    'backend/create_owner.py'
]

for f in files_to_process:
    process_file(f)

print("Done processing python files.")
