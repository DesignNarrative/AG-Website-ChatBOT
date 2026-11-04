import sqlite3
import uuid
import datetime

conn = sqlite3.connect("abhinav_chatbot_dev.db")
cur = conn.cursor()

cur.execute("SELECT id FROM projects WHERE project_id_slug = 'pebbles-business-bay'")
row = cur.fetchone()

if not row:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur.execute(
        """
        INSERT INTO projects (
            id, project_id_slug, project_name, project_type, project_status,
            location, address, city, state,
            configurations, rera_number, rera_verified, price_verified, possession_verified,
            description, approval_status, is_active, is_featured, version, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            str(uuid.uuid4()),
            "pebbles-business-bay",
            "Pebbles Business Bay",
            "COMMERCIAL",
            "ONGOING",
            "Wakad, Pune",
            (
                "Sr. No. 132(P), 121(P), Opp. Phoenix Mall of the Millennium, Near My"
                " Car showroom / Bhumkar Chowk, Wakad, Pune - 411057"
            ),
            "Pune",
            "Maharashtra",
            "Showrooms, Retail Spaces & Corporate Offices",
            "Registered",
            1,
            0,
            0,
            (
                "Premier commercial landmark in Wakad, Pune, opposite Phoenix"
                " Mall of the Millennium near Bhumkar Chowk. High-street retail"
                " showrooms and corporate office spaces with high footfall and"
                " expressway connectivity."
            ),
            "APPROVED",
            1,
            1,
            1,
            now,
            now,
        ),
    )
    conn.commit()
    print("Inserted Pebbles Business Bay successfully!")
else:
    print("Pebbles Business Bay already exists in DB.")

cur.execute(
    "SELECT project_id_slug, project_name, project_type, project_status FROM"
    " projects"
)
for r in cur.fetchall():
    print(r)

conn.close()
