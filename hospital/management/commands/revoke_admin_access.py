"""
Revoke admin/IT privileges from a user.

Usage examples:
  python manage.py revoke_admin_access --query rebecca
  python manage.py revoke_admin_access --username rebecca
  python manage.py revoke_admin_access --email rebecca@example.com
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models import Q


User = get_user_model()


ADMIN_LIKE_GROUPS = {
    "admin",
    "administrator",
    "administrators",
    "it",
    "it_staff",
    "it_operations",
    "it_support",
    "it operations",
}

ADMIN_PERMISSION_CODENAMES = {
    # Procurement admin approval
    "can_approve_procurement_admin",
}


def _normalize_group_name(name: str) -> str:
    return (name or "").strip().lower().replace("&", "and")


class Command(BaseCommand):
    help = "Revoke admin/IT privileges from a user (groups, perms, superuser)."

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, default=None, help="Exact username")
        parser.add_argument("--email", type=str, default=None, help="Exact email")
        parser.add_argument(
            "--query",
            type=str,
            default=None,
            help="Search term (username/first/last/email). If multiple matches found, command exits.",
        )

    def handle(self, *args, **options):
        username = options.get("username")
        email = options.get("email")
        query = options.get("query")

        qs = User.objects.all()

        user = None
        if username:
            user = qs.filter(username=username).first()
        elif email:
            user = qs.filter(email=email).first()
        elif query:
            matches = qs.filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
            ).order_by("username")
            count = matches.count()
            if count == 0:
                self.stdout.write(self.style.ERROR(f'❌ No users matched query "{query}".'))
                return
            if count > 1:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Multiple users matched query "{query}" ({count}). '
                        "Re-run with --username or --email."
                    )
                )
                for u in matches[:30]:
                    self.stdout.write(
                        f" - {u.username} | {u.get_full_name() or 'N/A'} | {u.email or 'N/A'}"
                    )
                if count > 30:
                    self.stdout.write(" (more matches not shown)")
                return
            user = matches.first()
        else:
            self.stdout.write(self.style.ERROR("❌ Provide --username, --email, or --query."))
            return

        if not user:
            self.stdout.write(self.style.ERROR("❌ User not found."))
            return

        self.stdout.write(self.style.SUCCESS(f"✅ Found user: {user.username}"))
        self.stdout.write(f"   Full name: {user.get_full_name() or 'N/A'}")
        self.stdout.write(f"   Email: {user.email or 'N/A'}")
        self.stdout.write("")

        changes = []

        # Remove superuser flag if present
        if user.is_superuser:
            user.is_superuser = False
            changes.append("is_superuser=False")

        # Remove admin-like groups
        removed_groups = []
        for g in list(user.groups.all()):
            g_norm = _normalize_group_name(g.name).replace(" ", "_")
            if g_norm in {n.replace(" ", "_") for n in ADMIN_LIKE_GROUPS} or "admin" in g_norm or g_norm.startswith("it"):
                user.groups.remove(g)
                removed_groups.append(g.name)
        if removed_groups:
            changes.append(f"removed_groups={', '.join(sorted(set(removed_groups)))}")

        # Remove admin-like direct user permissions
        removed_perms = []
        if ADMIN_PERMISSION_CODENAMES:
            perms = Permission.objects.filter(codename__in=ADMIN_PERMISSION_CODENAMES)
            for p in perms:
                if user.user_permissions.filter(id=p.id).exists():
                    user.user_permissions.remove(p)
                    removed_perms.append(p.codename)
        if removed_perms:
            changes.append(f"removed_user_permissions={', '.join(sorted(set(removed_perms)))}")

        if changes:
            user.save(update_fields=["is_superuser"])
            self.stdout.write(self.style.SUCCESS("✅ Revoked elevated privileges."))
            for c in changes:
                self.stdout.write(f"   - {c}")
        else:
            self.stdout.write(self.style.WARNING("⚠️ No admin/IT privileges found to revoke."))

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING("⚠️ IMPORTANT: The user must log out and log back in for menu/role changes to fully apply.")
        )

