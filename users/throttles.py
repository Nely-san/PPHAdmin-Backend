from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

class AuthLoginThrottle(AnonRateThrottle):
    """
    Restricts brute-force login attempts per IP address.
    Defaults to 5 requests per minute.
    """
    scope = 'auth_login'


class PasswordResetThrottle(AnonRateThrottle):
    """
    Restricts password reset request attempts per IP address to prevent spam.
    Defaults to 5 requests per hour.
    """
    scope = 'password_reset'
