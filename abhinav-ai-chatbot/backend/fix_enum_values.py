import sqlite3

conn = sqlite3.connect("abhinav_chatbot_dev.db")
cur = conn.cursor()

# 1. Fix User Role
cur.execute("UPDATE users SET role = 'DEVELOPER' WHERE email = 'ai.abhinavgroup@gmail.com'")
cur.execute("SELECT email, role FROM users")
print("User records:", cur.fetchall())

# 2. Fix Projects enum values
cur.execute("UPDATE projects SET project_type = 'RESIDENTIAL' WHERE project_type = 'residential'")
cur.execute("UPDATE projects SET project_type = 'COMMERCIAL' WHERE project_type = 'commercial'")
cur.execute("UPDATE projects SET project_status = 'ONGOING' WHERE project_status = 'ongoing'")
cur.execute("UPDATE projects SET project_status = 'COMPLETED' WHERE project_status = 'completed'")
cur.execute("UPDATE projects SET approval_status = 'APPROVED' WHERE approval_status = 'approved'")
cur.execute("UPDATE projects SET approval_status = 'PENDING' WHERE approval_status = 'pending'")

cur.execute("SELECT project_id_slug, project_type, project_status, approval_status FROM projects")
print("Project records:", cur.fetchall())

conn.commit()
conn.close()
print("Enum values updated successfully.")
