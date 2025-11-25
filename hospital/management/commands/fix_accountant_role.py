"""
Management command to fix Robbert Kwame Gbologah's role from administrator to accountant
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from hospital.models import Staff
from hospital.utils_roles import assign_user_to_role, ROLE_FEATURES


class Command(BaseCommand):
    help = 'Fix Robbert Kwame Gbologah role from administrator to accountant'

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("Fixing Accountant Role"))
        self.stdout.write("=" * 70)
        self.stdout.write("")
        
        # Try to find the user by various possible usernames
        possible_usernames = [
            'robbert.kwamegbologah',
            'robbert.kwame.gbologah',
            'robbertkwamegbologah',
            'robbert_gbologah',
        ]
        
        # Also search by name
        user = None
        try:
            # Search by username first
            for username in possible_usernames:
                try:
                    user = User.objects.get(username__iexact=username)
                    self.stdout.write(self.style.SUCCESS(f"✓ Found user by username: {username}"))
                    break
                except User.DoesNotExist:
                    continue
            
            # If not found by username, try by name
            if not user:
                try:
                    user = User.objects.filter(
                        first_name__icontains='robbert',
                        last_name__icontains='gbologah'
                    ).first()
                    if user:
                        self.stdout.write(self.style.SUCCESS(f"✓ Found user by name: {user.username}"))
                except Exception:
                    pass
            
            # If still not found, search by email
            if not user:
                try:
                    user = User.objects.filter(email__icontains='robbert').filter(
                        email__icontains='gbologah'
                    ).first()
                    if user:
                        self.stdout.write(self.style.SUCCESS(f"✓ Found user by email: {user.username}"))
                except Exception:
                    pass
            
            if not user:
                self.stdout.write(self.style.ERROR("✗ User not found. Searching all users..."))
                
                # List all users with similar names
                all_users = User.objects.filter(
                    first_name__icontains='robbert'
                ) | User.objects.filter(
                    last_name__icontains='gbologah'
                ) | User.objects.filter(
                    username__icontains='robbert'
                )
                
                if all_users.exists():
                    self.stdout.write("Found potential matches:")
                    for u in all_users:
                        self.stdout.write(f"  • {u.username} - {u.get_full_name()} - is_superuser: {u.is_superuser}")
                
                return
            
            # Show current status
            self.stdout.write("")
            self.stdout.write(f"Current User Info:")
            self.stdout.write(f"  Username: {user.username}")
            self.stdout.write(f"  Full Name: {user.get_full_name()}")
            self.stdout.write(f"  Email: {user.email}")
            self.stdout.write(f"  is_superuser: {user.is_superuser}")
            self.stdout.write(f"  is_staff: {user.is_staff}")
            self.stdout.write(f"  Groups: {', '.join([g.name for g in user.groups.all()])}")
            
            # Check for Staff record
            staff = None
            try:
                staff = Staff.objects.get(user=user, is_deleted=False)
                self.stdout.write(f"  Staff Profession: {staff.profession}")
                self.stdout.write(f"  Staff Department: {staff.department.name if staff.department else 'N/A'}")
            except Staff.DoesNotExist:
                self.stdout.write("  Staff Record: Not found")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Staff Record: Error - {e}"))
            
            self.stdout.write("")
            
            # Change role from admin to accountant
            self.stdout.write("Changing role from administrator to accountant...")
            
            # Remove superuser status
            user.is_superuser = False
            user.save(update_fields=['is_superuser'])
            self.stdout.write(self.style.SUCCESS("  ✓ Removed superuser status"))
            
            # Assign accountant role
            assign_user_to_role(user, 'accountant')
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Assigned role: {ROLE_FEATURES['accountant']['name']}"
            ))
            
            # Update Staff record if it exists
            if staff:
                # Change profession from 'admin' to 'accountant'
                old_profession = staff.profession
                staff.profession = 'accountant'
                staff.save(update_fields=['profession'])
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ Updated staff profession: {old_profession} → accountant"
                ))
            else:
                self.stdout.write(self.style.WARNING("  • No staff record found to update"))
            
            self.stdout.write("")
            self.stdout.write("=" * 70)
            self.stdout.write(self.style.SUCCESS("✓ Role change completed successfully!"))
            self.stdout.write("=" * 70)
            self.stdout.write("")
            self.stdout.write("New User Status:")
            user.refresh_from_db()
            self.stdout.write(f"  is_superuser: {user.is_superuser}")
            self.stdout.write(f"  is_staff: {user.is_staff}")
            self.stdout.write(f"  Groups: {', '.join([g.name for g in user.groups.all()])}")
            if staff:
                staff.refresh_from_db()
                self.stdout.write(f"  Staff Profession: {staff.profession}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())


