"""
Custom authentication backends for HMS
Supports both username and email authentication
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.conf import settings

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend that allows users to login with either
    username or email address. This is useful when ACCOUNT_AUTHENTICATION_METHOD
    is set to 'email' but you still want to support username login.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate using either username or email.
        """
        if username is None:
            username = kwargs.get('email')
        
        if username is None or password is None:
            return None
        
        try:
            # Try to find user by username first
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # If not found by username, try email
            try:
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                # User doesn't exist
                return None
            except User.MultipleObjectsReturned:
                # Multiple users with same email (shouldn't happen but handle it)
                return None
        
        # Check password
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None
    
    def get_user(self, user_id):
        """
        Get user by ID (required by Django authentication system)
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None




