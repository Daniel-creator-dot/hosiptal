# Fix Corporate Bills page (VariableDoesNotExist: payer)

The server at 192.168.2.216 is using **old** code. To see **all corporate bills** and remove the error, update the server with the latest code from this repo.

## Quick fix (template only) – on the server

Edit the file **on the server** (path inside container: `/app/hospital/templates/hospital/billing/company_bill_list.html`).

**Change line 65 from:**
```django
<td>{{ statement.corporate_account.company_name|default:statement.payer.name|default:"N/A" }}</td>
```

**To:**
```django
<td>{% if statement.corporate_account %}{{ statement.corporate_account.company_name|default:"N/A" }}{% else %}N/A{% endif %}</td>
```

Save the file and reload the Corporate Bills page.

## Full fix (recommended) – deploy latest code

1. **Pull/copy latest code** from this repo to the server (or rebuild the Docker image from this repo).
2. **Restart** the app container so it loads:
   - Updated **template** (no `statement.payer` → no error)
   - Updated **view** (`views_billing_claims.py`: corporate invoice summary, fallback corporate payers, `stmt.payer` set)

Then you get:
- All corporate bills (MonthlyStatements + corporate receivables + **invoices by corporate payer** + **all corporate payers** even with 0 invoices)
- No VariableDoesNotExist

## Copy single file into running Docker container

From your **local machine** (in the repo directory):

```bash
docker cp hospital/templates/hospital/billing/company_bill_list.html <CONTAINER_NAME>:/app/hospital/templates/hospital/billing/company_bill_list.html
```

Replace `<CONTAINER_NAME>` with the actual container name (`docker ps` to see it).
