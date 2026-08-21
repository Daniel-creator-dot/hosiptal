"""
IT Operations: remove duplicate staff logins and patient records.
Uses soft-delete so clinical/billing history is not destroyed.
"""
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from hospital.models import Staff, UserSession, Patient
from hospital.models_audit import AuditLog


PROTECTED_USERNAMES = frozenset({"admin"})


def is_protected_login(user):
    if not user:
        return False
    if user.is_superuser:
        return True
    return (user.username or "").strip().lower() in PROTECTED_USERNAMES


def revoke_login_sessions(user):
    """End Django sessions and HMS UserSession rows for this login."""
    revoked = 0
    if not user:
        return revoked
    uid = str(user.id)
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        try:
            data = session.get_decoded()
        except Exception:
            continue
        if str(data.get("_auth_user_id") or "") == uid:
            session.delete()
            revoked += 1
    UserSession.objects.filter(user=user, is_active=True, logout_time__isnull=True).update(
        is_active=False,
        logout_time=timezone.now(),
    )
    return revoked


def _audit(*, actor, action_type, model_name, object_id, object_repr, description, request=None):
    try:
        AuditLog.log_action(
            user=actor,
            action_type=action_type,
            model_name=model_name,
            object_id=str(object_id),
            object_repr=object_repr,
            description=description,
            severity="warning",
            ip_address=(request.META.get("REMOTE_ADDR") if request else None),
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
            request_path=(request.path if request else ""),
            request_method=(request.method if request else ""),
        )
    except Exception:
        pass


def delete_patient_record(*, patient, performed_by, reason="", request=None):
    if not patient or patient.is_deleted:
        raise ValidationError("This patient is already removed from the system.")

    with transaction.atomic():
        locked = Patient.objects.select_for_update().filter(pk=patient.pk, is_deleted=False).first()
        if not locked:
            raise ValidationError("This patient is already removed from the system.")
        locked.is_deleted = True
        locked.save(update_fields=["is_deleted", "modified"])

    label = f"{locked.full_name} ({locked.mrn})"
    note = (reason or "").strip()
    desc = f"Removed duplicate/unwanted patient record: {label}"
    if note:
        desc += f". Reason: {note}"
    _audit(
        actor=performed_by,
        action_type="delete",
        model_name="Patient",
        object_id=locked.id,
        object_repr=label,
        description=desc,
        request=request,
    )
    return locked


def delete_login_account(*, user, performed_by, reason="", request=None):
    if not user:
        raise ValidationError("Login account not found.")
    if performed_by and user.id == performed_by.id:
        raise ValidationError("You cannot delete your own account.")
    if is_protected_login(user):
        raise ValidationError("Administrator accounts cannot be deleted.")

    username = user.username
    staff = Staff.objects.filter(user=user, is_deleted=False).first()

    with transaction.atomic():
        if staff:
            locked_staff = Staff.objects.select_for_update().filter(pk=staff.pk, is_deleted=False).first()
            if locked_staff:
                locked_staff.is_deleted = True
                locked_staff.is_active = False
                locked_staff.save(update_fields=["is_deleted", "is_active", "modified"])
        user.is_active = False
        user.save(update_fields=["is_active"])
        revoked = revoke_login_sessions(user)

    note = (reason or "").strip()
    desc = f"Removed duplicate/unwanted login: {username}"
    if staff:
        desc += f" (staff {staff.employee_id})"
    desc += f". Sessions revoked: {revoked}."
    if note:
        desc += f" Reason: {note}"
    _audit(
        actor=performed_by,
        action_type="delete",
        model_name="User",
        object_id=user.id,
        object_repr=username,
        description=desc,
        request=request,
    )
    return user
