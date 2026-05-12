import sqlite3
import os

# Adjust the path if your db is in the main folder instead of /instance
db_path = 'instance/seds.db'

if not os.path.exists(db_path):
    db_path = 'seds.db'

try:
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # The magic command to add the column
    cursor.execute("ALTER TABLE emergency_log ADD COLUMN image_file VARCHAR(100);")
    
    conn.commit()
    conn.close()
    print("✅ Success! The 'image_file' column was added without deleting your data.")

except sqlite3.OperationalError as e:
    print(f"⚠️ Note: {e} (This might mean the column already exists)")
except Exception as e:
    print(f"❌ Error: {e}")