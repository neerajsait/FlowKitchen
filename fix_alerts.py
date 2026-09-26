import os
import re

directories = [
    'frontend-admin/src/components',
    'frontend-customer/src/components'
]

def fix_alerts(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Replace alert(`...`) and alert("...") with showToast(..., type)
    # where type is 'error' if it contains 'fail' or 'error'
    
    def replacer(match):
        inner = match.group(1)
        if 'fail' in inner.lower() or 'error' in inner.lower():
            return f'showToast({inner}, "error")'
        else:
            return f'showToast({inner}, "success")'

    # Match alert( SOMETHING )
    content = re.sub(r'alert\((.*?)\)', replacer, content)

    # Remove the wrapper definitions if they exist
    content = re.sub(r'// Legacy alert.*?};\n', '', content, flags=re.DOTALL)
    content = re.sub(r'const alert\s*=\s*\(msg\)\s*=>\s*\{.*?\};\n', '', content, flags=re.DOTALL)
    content = re.sub(r'const alert = showAlert;\n', '', content)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed alerts in {filepath}")

for d in directories:
    if os.path.exists(d):
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith('.jsx'):
                    fix_alerts(os.path.join(root, file))

# Fix api.js separately
for api_path in ['frontend-admin/src/utils/api.js', 'frontend-customer/src/utils/api.js']:
    if os.path.exists(api_path):
        with open(api_path, 'r', encoding='utf-8') as f:
            c = f.read()
        c = c.replace('alert("Warning: Could not reach the server', 'console.warn("Warning: Could not reach the server')
        with open(api_path, 'w', encoding='utf-8') as f:
            f.write(c)

print("Done fixing alerts.")
