"""
Middleware to restrict midwives from non-clinical areas (finance, pharmacy dispensing, HR admin, etc.)
while allowing the same inpatient and nursing workflows as nurses: admissions, beds, vitals, orders, triage, etc.
"""
import logging

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse

from .utils_roles import get_user_role

logger = logging.getLogger(__name__)

# URL patterns that midwives are allowed to access
MIDWIFE_ALLOWED_PATTERNS = [
    '/hms/midwife',  # All midwife URLs
    '/hms/dashboard/midwife',  # Midwife dashboard
    '/hms/dashboard/nurse',  # Nurse dashboard (also accessible)
    '/hms/patients',  # Patient management (for maternity patients)
    '/hms/patient',  # Patient URLs
    '/hms/encounter',  # Encounters (antenatal, postnatal visits)
    '/hms/vitals',  # Vital signs
    '/hms/triage',  # Triage (same as nurses)
    '/hms/admissions',  # Admission list and create
    '/hms/beds',  # Bed management
    '/hms/admitted-patients',  # Admitted patients / handover
    '/hms/nurse',  # Nurse flowboard and nurse URLs shared with midwives
    '/hms/orders',  # Clinical orders
    '/hms/medical-records',  # Medical records list/detail
    '/hms/screening',  # Pre-employment / pre-admission screening (same as nurses)
    '/hms/flow',  # Patient flow / vitals workflow routes
    '/hms/search',  # Global patient search (used from nurse tools)
    '/hms/appointment',  # Appointments (for scheduling maternity visits)
    '/hms/staff',  # Staff portal - midwives are staff members
    '/hms/staff/portal',  # Staff portal dashboard
    '/hms/staff/leave',  # Staff leave requests
    '/hms/staff/activities',  # Staff activities calendar
    '/hms/staff/notifications',  # Staff notifications
    '/hms/staff/dashboard',  # Staff dashboard
    '/hms/staff/my-schedule',  # Staff schedule view
    '/hms/logout',
    '/hms/login',
    '/hms/static',
    '/hms/media',
    '/hms/documents',  # Authenticated patient document files (lab/imaging PDFs)
    '/api/notifications',  # Allow notifications API
    '/api/hospital/patient',  # Patient API
    '/api/hospital/encounter',  # Encounter API
    '/api/hospital/vitalsign',  # Vital signs API
    '/hms/notifications/mark-all-read',  # Allow notification actions
    '/hms/notifications/clear-all',  # Clear all notifications
    '/hms/notifications/',  # Allow notifications list
    '/hms/chat/',  # Staff direct messaging (available to all authenticated users)
]


class MidwifeRestrictionMiddleware:
    """
    Middleware to keep midwives out of finance, pharmacy, lab, imaging, and admin modules
    while allowing shared clinical paths with nurses (admissions, beds, vitals, triage, orders, etc.).
    Default-deny: any path not in MIDWIFE_ALLOWED_PATTERNS is blocked.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        user_role = getattr(request, 'hms_user_role', None)
        if user_role is None:
            user_role = get_user_role(request.user, request)

        if user_role != 'midwife':
            return self.get_response(request)

        path = request.path
        if any(path.startswith(pattern) for pattern in MIDWIFE_ALLOWED_PATTERNS):
            return self.get_response(request)

        messages.warning(
            request,
            'Access denied. You only have access to clinical and maternity care features.',
        )
        try:
            return redirect('hospital:midwife_dashboard')
        except NoReverseMatch:
            logger.exception('midwife_dashboard URL not found; using fallback redirect')
            return redirect('/hms/dashboard/midwife/')
        except Exception:
            logger.exception('Unexpected error redirecting midwife to dashboard')
            return redirect('/hms/dashboard/midwife/')
