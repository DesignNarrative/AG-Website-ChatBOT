import os, sys, uuid, datetime

sys.path.insert(0, ".")

from app.security.auth import hash_password
import sqlite3

db_path = "abhinav_chatbot_dev.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 1. Seed or update user
email = "ai.abhinavgroup@gmail.com"
raw_pw = "abhinav@2026@"
hashed = hash_password(raw_pw)
user_id = str(uuid.uuid4())
now = datetime.datetime.now(datetime.timezone.utc).isoformat()

# Check if user already exists
cur.execute("SELECT id FROM users WHERE email = ?", (email,))
existing = cur.fetchone()

if existing:
    cur.execute(
        "UPDATE users SET hashed_password = ?, role = 'DEVELOPER', is_active = 1, updated_at = ? WHERE email = ?",
        (hashed, now, email)
    )
    print(f"Updated existing user: {email} with role: DEVELOPER")
else:
    cur.execute(
        "INSERT INTO users (id, email, full_name, hashed_password, role, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, email, "Abhinav Group Administrator", hashed, "DEVELOPER", 1, now, now)
    )
    print(f"Created new user: {email} with role: DEVELOPER")

# 2. Seed projects if empty
cur.execute("SELECT COUNT(*) FROM projects")
count = cur.fetchone()[0]

if count == 0:
    projects = [
        (
            str(uuid.uuid4()), "samsara", "Samsara", "RESIDENTIAL", "ONGOING",
            "Mukund Nagar", "Mukund Nagar, Pune, Maharashtra", "Pune", "Maharashtra",
            "3 BHK Luxury Residences", "P52100079797", 0, 0, 0,
            "Luxury 3 BHK residences in the heart of Mukund Nagar, Pune with world-class amenities.",
            "APPROVED", 1, 0, 1, now, now
        ),
        (
            str(uuid.uuid4()), "pebbles-greenfield", "Pebbles Greenfield", "RESIDENTIAL", "ONGOING",
            "Tathawade / Wakad", "Tathawade, Wakad, Pune, Maharashtra", "Pune", "Maharashtra",
            "2 & 3 BHK", "P52100045923", 0, 0, 0,
            "Premium 2 & 3 BHK residences with modern landscape amenities and seamless highway connectivity.",
            "APPROVED", 1, 0, 1, now, now
        ),
        (
            str(uuid.uuid4()), "the-curve", "The Curve", "RESIDENTIAL", "ONGOING",
            "Virar West", "Virar West, Mumbai MMR, Maharashtra", "Virar", "Maharashtra",
            "2 & 3 BHK", "PR1240002600667", 0, 0, 0,
            "Modern 2 & 3 BHK waterfront-facing apartments in Virar West, Mumbai MMR. Possession target June 2031.",
            "APPROVED", 1, 0, 1, now, now
        ),
        (
            str(uuid.uuid4()), "aeromall", "Aeromall", "COMMERCIAL", "COMPLETED",
            "Airport Road, Lohegaon", "Pune Airport Road, Lohegaon, Pune, Maharashtra", "Pune", "Maharashtra",
            "Retail & Commercial Spaces", "Commercial Facility", 0, 0, 0,
            "Pune's first 24x7 integrated shopping, dining, and multi-level parking commercial complex.",
            "APPROVED", 1, 0, 1, now, now
        ),
    ]

    for p in projects:
        cur.execute(
            """INSERT INTO projects (
                id, project_id_slug, project_name, project_type, project_status,
                location, address, city, state,
                configurations, rera_number, rera_verified, price_verified, possession_verified,
                description, approval_status, is_active, is_featured, version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            p
        )
    print("Seeded 4 official projects into database.")
else:
    print(f"Projects table already has {count} records.")

conn.commit()
conn.close()
print("Database seeding completed successfully.")
