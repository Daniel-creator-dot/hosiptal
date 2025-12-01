# Import Legacy Patients - Fix Applied

## Problem
The `import_legacy_patients` command was failing silently due to a Unicode encoding issue. The checkmark character (✓) in the success message couldn't be encoded in Windows PowerShell's default code page.

## Fixes Applied

1. **Replaced Unicode characters** with ASCII-safe alternatives:
   - Changed `✓` to `[OK]` in success messages

2. **Added better error handling**:
   - Added try-catch blocks with detailed error messages
   - Added debug output to track progress

3. **Improved file reading**:
   - Added error handling for file operations
   - Added progress indicators

## How to Run

### Option 1: Using the batch file (Recommended for Windows)
```batch
run_import_legacy.bat
```

Or with additional options:
```batch
run_import_legacy.bat --limit 100
run_import_legacy.bat --dry-run
```

### Option 2: Direct command with UTF-8 encoding
```powershell
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
py -3 -u manage.py import_legacy_patients --sql-dir import\legacy --patients-only
```

### Option 3: Using the Python wrapper
```powershell
py -3 run_import.py
```

### Option 4: Redirect output to file
```powershell
py -3 manage.py import_legacy_patients --sql-dir import\legacy --patients-only > import_output.txt 2>&1
Get-Content import_output.txt
```

## Command Options

- `--sql-dir`: Directory containing SQL files (default: `import\legacy`)
- `--patients-only`: Import only patients, skip insurance linking
- `--insurance-only`: Import only insurance links, skip patients
- `--dry-run`: Perform a dry run without actually importing data
- `--limit N`: Limit number of records to import (for testing)

## Example Usage

```powershell
# Import first 10 patients (test run)
py -3 manage.py import_legacy_patients --sql-dir import\legacy --patients-only --limit 10

# Dry run to see what would be imported
py -3 manage.py import_legacy_patients --sql-dir import\legacy --patients-only --dry-run --limit 100

# Full import (all patients)
py -3 manage.py import_legacy_patients --sql-dir import\legacy --patients-only
```

## Troubleshooting

If you still don't see output:

1. **Check if the command is actually running**: Look for the `patient_data.sql` file being processed
2. **Check the database**: Verify if patients are being imported by checking the Patient table
3. **Use file redirection**: Redirect output to a file to see what's happening
4. **Check file permissions**: Ensure the SQL files are readable

## Files Modified

- `hospital/management/commands/import_legacy_patients.py`: Fixed Unicode encoding issues and added better error handling


