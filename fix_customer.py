import re

files = [
    'frontend-customer/src/utils/api.js',
    'frontend-customer/src/components/CustomerView.jsx',
    'frontend-customer/src/components/ProfilePage.jsx',
]

for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replacements
    c = content.replace('first_name = "", last_name = ""', 'full_name = ""')
    c = c.replace('first_name, last_name,', 'full_name,')
    c = c.replace('first_name: "", last_name: ""', 'full_name: ""')
    c = c.replace('currentUser?.first_name || guestName || ""', 'currentUser?.full_name || guestName || ""')
    c = c.replace('[user.first_name, user.last_name].filter(Boolean).join(" ")', 'user.full_name')
    c = c.replace('first_name: user.first_name || "", last_name: user.last_name || ""', 'full_name: user.full_name || ""')
    c = c.replace('["First Name", user.first_name || "—"], ["Last Name", user.last_name || "—"]', '["Full Name", user.full_name || "—"]')
    c = c.replace('profileForm.first_name', 'profileForm.full_name')
    c = c.replace('first_name: e.target.value', 'full_name: e.target.value')
    
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(c)

print('Done frontend-customer full_name replacements')
