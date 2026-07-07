"""
Resolve HMS user role once per request (after auth) to avoid duplicate Staff/group queries
in downstream middleware and views.
"""
from .utils_roles import attach_user_role_to_request


class RequestUserRoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        attach_user_role_to_request(request)
        return self.get_response(request)
