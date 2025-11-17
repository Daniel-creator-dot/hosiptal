from django.contrib.auth.views import LoginView


class HMSLoginView(LoginView):
    """
    Simple HMS login view that sends all users to the main dashboard after login.
    Uses Django's built-in authentication with CSRF protection.
    """
    template_name = "hospital/login.html"
    redirect_authenticated_user = True




