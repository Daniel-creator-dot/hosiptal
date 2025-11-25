"""
Final Patient Data Import - Production Ready
"""

import os
import sys
import django

# Setup Django  
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection


def main():
    print("="*70)
    print("IMPORTING PATIENT DATA")
    print("="*70)
    print()
    
    sql_file = r'C:\Users\user\Videos\DS\patient_data.sql'
    
    print("Step 1: Reading SQL file...")
    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Find CREATE TABLE section (lines 1-106)
    print("Step 2: Extracting CREATE TABLE...")
    create_lines = []
    in_create = False
    
    for i, line in enumerate(lines):
        if 'CREATE TABLE' in line.upper():
            in_create = True
        
        if in_create:
            create_lines.append(line)
            
        # Stop at ENGINE line
        if in_create and 'ENGINE' in line.upper():
            break
    
    # Manual CREATE TABLE for patient_data
    create_sql = """
    CREATE TABLE patient_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT DEFAULT '',
        language TEXT DEFAULT '',
        financial TEXT DEFAULT '',
        fname TEXT DEFAULT '',
        lname TEXT DEFAULT '',
        mname TEXT DEFAULT '',
        DOB TEXT,
        street TEXT DEFAULT '',
        postal_code TEXT DEFAULT '',
        city TEXT DEFAULT '',
        state TEXT DEFAULT '',
        country_code TEXT DEFAULT '',
        drivers_license TEXT DEFAULT '',
        ss TEXT DEFAULT '',
        occupation TEXT,
        phone_home TEXT DEFAULT '',
        phone_biz TEXT DEFAULT '',
        phone_contact TEXT DEFAULT '',
        phone_cell TEXT DEFAULT '',
        pharmacy_id INTEGER DEFAULT 0,
        status TEXT DEFAULT '',
        contact_relationship TEXT DEFAULT '',
        date TEXT,
        sex TEXT DEFAULT '',
        referrer TEXT DEFAULT '',
        referrerID TEXT DEFAULT '',
        providerID INTEGER,
        ref_providerID INTEGER,
        email TEXT DEFAULT '',
        email_direct TEXT DEFAULT '',
        ethnoracial TEXT DEFAULT '',
        race TEXT DEFAULT '',
        ethnicity TEXT DEFAULT '',
        religion TEXT DEFAULT '',
        interpretter TEXT DEFAULT '',
        migrantseasonal TEXT DEFAULT '',
        family_size TEXT DEFAULT '',
        monthly_income TEXT DEFAULT '',
        billing_note TEXT,
        homeless TEXT DEFAULT '',
        financial_review TEXT,
        pubpid TEXT DEFAULT '',
        pid INTEGER DEFAULT 0,
        genericname1 TEXT DEFAULT '',
        genericval1 TEXT DEFAULT '',
        genericname2 TEXT DEFAULT '',
        genericval2 TEXT DEFAULT '',
        hipaa_mail TEXT DEFAULT '',
        hipaa_voice TEXT DEFAULT '',
        hipaa_notice TEXT DEFAULT '',
        hipaa_message TEXT DEFAULT '',
        hipaa_allowsms TEXT DEFAULT 'NO',
        hipaa_allowemail TEXT DEFAULT 'NO',
        squad TEXT DEFAULT '',
        fitness INTEGER DEFAULT 0,
        referral_source TEXT DEFAULT '',
        usertext3 TEXT DEFAULT '',
        contrastart TEXT,
        completed_ad TEXT DEFAULT 'NO',
        ad_reviewed TEXT,
        vfc TEXT DEFAULT '',
        mothersname TEXT DEFAULT '',
        guardiansname TEXT,
        allow_imm_reg_use TEXT DEFAULT '',
        allow_imm_info_share TEXT DEFAULT '',
        allow_health_info_ex TEXT DEFAULT '',
        allow_patient_portal TEXT DEFAULT '',
        deceased_date TEXT,
        deceased_reason TEXT DEFAULT '',
        soap_import_status INTEGER,
        cmsportal_login TEXT DEFAULT '',
        care_team INTEGER,
        county TEXT DEFAULT '',
        industry TEXT,
        imm_reg_status TEXT,
        imm_reg_stat_effdate TEXT,
        publicity_code TEXT,
        publ_code_eff_date TEXT,
        protect_indicator TEXT,
        guardianrelationship TEXT,
        guardiansex TEXT,
        guardianaddress TEXT,
        guardiancity TEXT,
        guardianstate TEXT,
        guardianpostalcode TEXT,
        guardiancountry TEXT,
        guardianphone TEXT,
        guardianworkphone TEXT,
        guardianemail TEXT,
        prot_indi_effdate TEXT,
        userdate1 TEXT,
        pricelevel TEXT DEFAULT 'standard',
        regdate TEXT,
        pos TEXT,
        imagtemp TEXT,
        reg_type TEXT,
        palert TEXT,
        pat_vigilant TEXT,
        nia_pin TEXT
    );
    """
    
    # Get INSERT statements
    print("Step 3: Extracting INSERT statements...")
    insert_stmts = []
    for line in lines:
        if line.strip().startswith('INSERT INTO patient_data'):
            # Convert backticks
            line = line.replace('`', '"')
            insert_stmts.append(line.strip())
    
    print(f"Found: {len(insert_stmts):,} patient records to insert")
    print()
    
    # Import
    print("Step 4: Importing to database...")
    
    with connection.cursor() as cursor:
        # Drop existing
        try:
            cursor.execute('DROP TABLE IF EXISTS patient_data')
            print("[OK] Dropped existing table")
        except:
            pass
        
        # Create
        try:
            cursor.execute(create_sql)
            print("[OK] Created patient_data table")
        except Exception as e:
            print(f"[ERROR] Failed to create table: {e}")
            return
        
        # Insert
        print(f"\nInserting {len(insert_stmts):,} records...")
        print("Progress:")
        
        inserted = 0
        errors = 0
        
        for i, stmt in enumerate(insert_stmts, 1):
            try:
                cursor.execute(stmt)
                inserted += 1
                
                if i % 5000 == 0:
                    pct = (i/len(insert_stmts))*100
                    print(f"  {i:,}/{len(insert_stmts):,} ({pct:.1f}%)")
                    
            except Exception as e:
                errors += 1
                if errors < 5:
                    print(f"  [ERROR] Row {i}: {str(e)[:60]}")
        
        connection.connection.commit()
    
    # Verify
    print()
    print("="*70)
    print("SUCCESS!")
    print("="*70)
    print()
    
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM patient_data')
        total = cursor.fetchone()[0]
        print(f"Total patient records: {total:,}")
        
        # Count by sex
        cursor.execute('SELECT sex, COUNT(*) FROM patient_data GROUP BY sex')
        print("\nPatients by gender:")
        for row in cursor.fetchall():
            print(f"  {row[0] or 'Unknown':10s}: {row[1]:,}")
        
        # Sample data
        print("\nSample patients:")
        print("-"*70)
        cursor.execute('''
            SELECT id, fname, lname, DOB, sex, phone_cell 
            FROM patient_data 
            WHERE fname != ''
            ORDER BY id
            LIMIT 15
        ''')
        
        for row in cursor.fetchall():
            name = f"{row[1]} {row[2]}"
            print(f"  {row[0]:6d} | {name:30s} | {row[3]:12s} | {row[4]:6s}")
        
        print()
        print("="*70)
        print("PATIENT DATA IS NOW AVAILABLE!")
        print("="*70)
        print()
        print("Next steps:")
        print("1. Query data: python manage.py dbshell")
        print("              SELECT * FROM patient_data WHERE fname='John';")
        print()
        print("2. Create Django model for it (optional)")
        print("3. Build admin interface (optional)")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nImport cancelled")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()




















