# 🧑‍⚕️ Role Setup & Login Access

Use these steps after deploying so doctors, pharmacists, cashiers, etc. get the right dashboards automatically.

## 1. Make sure your staff profiles are linked to users
Each record in `hospital_staff` must have:
- `user` (auth user)
- `profession` (e.g. `doctor`, `pharmacist`, `nurse`, `lab_technician`, `receptionist`, `cashier`, `store_manager`)
- `is_active=True` and `is_deleted=False`

You can import staff profiles with `python manage.py import_staff staff.csv` or create them in the admin site.

## 2. Create role groups + permissions
Run once after migrations:
```
python manage.py setup_rbac
```
This command builds the Django groups and assigns their permissions based on `hospital/utils_roles.py`.

## 3. Auto-assign users to the right roles
```
python manage.py assign_roles --create-groups
```
- `--create-groups` ensures the display names like “Doctor” or “Pharmacist” exist.
- The command reads the staff profession and adds the user to the matching group.

You will see a summary such as:
```
✓ john.doe → Doctor
✓ mary.adjei → Pharmacist
```

## 4. Manually override a specific user
```
python manage.py assign_roles --username alice --role pharmacist
```
Valid role slugs are listed in `ROLE_FEATURES` (`doctor`, `nurse`, `pharmacist`, `lab_technician`, `receptionist`, `cashier`, `store_manager`, `accountant`, `hr_manager`, etc.).

## 5. Login experience
Once a user signs in:
1. `hospital.utils_roles.get_user_role()` resolves their primary role (superusers default to `admin`).
2. `hospital.views.dashboard` redirects them to the role-specific dashboard (pharmacy, lab, cashier, etc.).
3. Navigation menus come from `get_role_navigation()` so each role only sees its modules.

**Need to guard a new view?**
- Use `@role_required('pharmacist')` (from `hospital.decorators`) on function-based views.
- For class-based views inherit `RoleRequiredMixin` and set `allowed_roles = ('pharmacist',)`.
- Both helpers render `hospital/access_denied.html` automatically when someone without the role attempts access.

## 6. Verifying access
```
python manage.py shell
```
```python
from django.contrib.auth.models import User
from hospital.utils_roles import get_user_role, get_user_dashboard_url
user = User.objects.get(username="alice")
print(get_user_role(user))
print(get_user_dashboard_url(user))
```

If the output matches the expected dashboard URL, the user can log in and land on the correct workspace.

## 7. Keeping roles in sync
- Re-run `assign_roles` whenever you bulk-import staff or change professions.
- Include the command in your deployment checklist to guarantee new environments have the correct RBAC state.

With these steps, doctors, pharmacists, nurses, lab techs, and cashiers all land on the correct dashboards immediately after login.

