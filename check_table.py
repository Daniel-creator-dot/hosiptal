import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hospital_staffbiometric';")
result = cursor.fetchone()

if result:
    print("[OK] hospital_staffbiometric table EXISTS!")
else:
    print("[ERROR] hospital_staffbiometric table NOT FOUND - creating it now...")
    
    # Create the table
    cursor.execute("""
        CREATE TABLE hospital_staffbiometric (
            id TEXT PRIMARY KEY,
            created DATETIME NOT NULL,
            modified DATETIME NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT 0,
            staff_id TEXT NOT NULL,
            biometric_type_id TEXT NOT NULL,
            template_hash TEXT UNIQUE NOT NULL,
            template_data BLOB NOT NULL,
            template_metadata TEXT NOT NULL,
            enrolled_at DATETIME NOT NULL,
            enrolled_by_id INTEGER,
            enrollment_device TEXT,
            enrollment_location TEXT,
            quality_score DECIMAL(5,2) NOT NULL,
            sample_count INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            is_primary BOOLEAN NOT NULL DEFAULT 0,
            expires_at DATETIME,
            last_verified DATETIME,
            verification_count INTEGER NOT NULL DEFAULT 0,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until DATETIME,
            backup_method TEXT NOT NULL DEFAULT 'password',
            FOREIGN KEY (staff_id) REFERENCES hospital_staff(id),
            FOREIGN KEY (biometric_type_id) REFERENCES hospital_biometrictype(id),
            FOREIGN KEY (enrolled_by_id) REFERENCES auth_user(id)
        );
    """)
    
    conn.commit()
    print("[OK] Table created successfully!")

conn.close()
print("\n[DONE] All tables ready!")




















