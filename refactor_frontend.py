import os

def process_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Generic Replacements for AdminView.jsx
    content = content.replace('const [staffFirstName, setStaffFirstName] = useState("");\n  const [staffLastName, setStaffLastName] = useState("");', 'const [staffFullName, setStaffFullName] = useState("");')
    
    content = content.replace('setStaffFirstName(""); setStaffLastName("");', 'setStaffFullName("");')
    content = content.replace('setStaffFirstName(user.first_name || "");\n    setStaffLastName(user.last_name || "");', 'setStaffFullName(user.full_name || "");')
    
    content = content.replace('first_name: staffFirstName,\n        last_name: staffLastName,', 'full_name: staffFullName,')

    # Generic Replacements for all files
    content = content.replace('first_name: "", last_name: "",', 'full_name: "",')
    content = content.replace('first_name: user?.first_name || "",\n        last_name: user?.last_name || "",', 'full_name: user?.full_name || "",')
    
    # OutletOwnerView specific
    content = content.replace('first_name: staff.first_name || "",\n      last_name: staff.last_name || "",', 'full_name: staff.full_name || "",')
    content = content.replace('first_name: "", last_name: "", email: "",', 'full_name: "", email: "",')
    content = content.replace('first_name: "", last_name: "", phone: "",', 'full_name: "", phone: "",')
    
    # JSX interpolation Replacements
    content = content.replace('`${user.first_name || ""} ${user.last_name || ""}`.toLowerCase()', '(user.full_name || "").toLowerCase()')
    content = content.replace('{user.first_name || ""} {user.last_name || ""}', '{user.full_name || ""}')
    content = content.replace('{c.first_name} {c.last_name}', '{c.full_name}')
    content = content.replace('{u.first_name || u.email} {u.last_name || ""}', '{u.full_name || u.email}')
    content = content.replace('{u.first_name} {u.last_name}', '{u.full_name}')
    content = content.replace('walletTargetUser?.first_name', 'walletTargetUser?.full_name')

    # Profile Forms JSX Inputs
    content = content.replace('''<div className="grid-responsive-2col" style={{ gap: "1rem" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">First Name</label>
                <input type="text" className="form-input" value={profileForm.first_name} onChange={e => setProfileForm({ ...profileForm, first_name: e.target.value })} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Last Name</label>
                <input type="text" className="form-input" value={profileForm.last_name} onChange={e => setProfileForm({ ...profileForm, last_name: e.target.value })} />
              </div>
            </div>''', '''<div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Full Name</label>
              <input type="text" className="form-input" value={profileForm.full_name} onChange={e => setProfileForm({ ...profileForm, full_name: e.target.value })} />
            </div>''')
            
    # Add Staff / Edit Staff JSX Inputs AdminView
    content = content.replace('''<div className="grid-responsive-2col" style={{ gap: "0.75rem" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">First Name</label>
                <input type="text" autoComplete="off" className="form-input" value={staffFirstName} onChange={e => setStaffFirstName(e.target.value)} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Last Name</label>
                <input type="text" autoComplete="off" className="form-input" value={staffLastName} onChange={e => setStaffLastName(e.target.value)} />
              </div>
            </div>''', '''<div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Full Name</label>
              <input type="text" autoComplete="off" className="form-input" value={staffFullName} onChange={e => setStaffFullName(e.target.value)} />
            </div>''')
            
    # Add Staff OutletOwnerView
    content = content.replace('''<div className="grid-responsive-2col" style={{ gap: "1rem" }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">First Name</label>
              <input type="text" className="form-input" required value={addStaffForm.first_name} onChange={e => setAddStaffForm({ ...addStaffForm, first_name: e.target.value })} />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Last Name</label>
              <input type="text" className="form-input" required value={addStaffForm.last_name} onChange={e => setAddStaffForm({ ...addStaffForm, last_name: e.target.value })} />
            </div>
          </div>''', '''<div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Full Name</label>
            <input type="text" className="form-input" required value={addStaffForm.full_name} onChange={e => setAddStaffForm({ ...addStaffForm, full_name: e.target.value })} />
          </div>''')
          
    # Edit Staff OutletOwnerView
    content = content.replace('''<div className="grid-responsive-2col" style={{ gap: "1rem" }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">First Name</label>
              <input type="text" className="form-input" required value={editStaffForm.first_name} onChange={e => setEditStaffForm({ ...editStaffForm, first_name: e.target.value })} />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Last Name</label>
              <input type="text" className="form-input" required value={editStaffForm.last_name} onChange={e => setEditStaffForm({ ...editStaffForm, last_name: e.target.value })} />
            </div>
          </div>''', '''<div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Full Name</label>
            <input type="text" className="form-input" required value={editStaffForm.full_name} onChange={e => setEditStaffForm({ ...editStaffForm, full_name: e.target.value })} />
          </div>''')

    # Catch-all for first_name / last_name replacements
    # Need to be very careful to only do this for the stragglers if we missed anything
    content = content.replace("first_name", "full_name")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for f in ['frontend-admin/src/components/AdminView.jsx', 'frontend-admin/src/components/OutletOwnerView.jsx', 'frontend-admin/src/components/StaffPOS.jsx']:
    process_file(f)

print("Frontend scripts processed.")
