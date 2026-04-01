# Verify recent changes are visible

All code changes are in place. If you don't see them in the browser, try the following.

## 1. Restart the Django server

- Stop the current runserver (Ctrl+C in the terminal where it runs).
- Start it again: `python manage.py runserver`
- Django usually auto-reloads on file save; a full restart ensures no stale state.

**If you run with DEBUG=False (production):** template changes are cached. Either:
- Run `python manage.py clear_template_cache` then restart the server, or
- Temporarily set `DEBUG=True` in `.env` / settings to see template updates without cache.

## 2. Hard refresh the browser

- **Windows/Linux:** `Ctrl + Shift + R` or `Ctrl + F5`
- **Mac:** `Cmd + Shift + R`
- Or open the site in an Incognito/Private window to avoid cache.

## 3. Where to see each change

| Change | Where to look |
|--------|----------------|
| **Discharge button** | **Admission Review** page: go to **Admitted Patients** → click a patient's "Review" / "Admission Review" link. The action row should show six buttons: Add Progress Note, Add Medication, Update Status, Order Labs, Order Scans, **Discharge** (red). URL like `/admission-review/<uuid>/`. |
| **Notes append (no replace)** | **Admission Review** → Add Progress Note → save several different notes. Each save should add a new note; the list should grow (no overwrite). |
| **Doctor notes + Nurse notes** | **Encounter Full Record** (Full Profile / view encounter): separate "Doctor Notes" and "Nurse Notes" sections, plus "Other Clinical Notes". |
| **All notes on profile/records** | **Patient Records** / **Comprehensive Medical Record** (Full Profile): "All Clinical Notes" with every type (progress, SOAP, consultation, etc.). |

## 4. If Discharge is greyed out

- The red **Discharge** button is only clickable when the encounter has an **active admission** (status = admitted).
- If you see a grey "Discharge" button with tooltip "No active admission record", the encounter is not linked to an admitted admission in the database. Use an encounter that was opened from **Admitted Patients** so it has an admission.

## 5. Run a quick check

From project root:

```bash
python manage.py check
```

Should report: `System check identified no issues`.
