import sys, re
path = r'd:\python project\food\frontend-admin\src\components\AdminView.jsx'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('e.g. Summer Sale \ufffd\u201d 20% Off Everything', 'e.g. Summer Sale — 20% Off Everything')
text = text.replace('e.g. Summer Sale \ufffd" 20% Off Everything', 'e.g. Summer Sale — 20% Off Everything')
text = text.replace('\ufffd10', '?10')
text = text.replace('\ufffd1', '?1')
text = text.replace('\ufffd', '?')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
