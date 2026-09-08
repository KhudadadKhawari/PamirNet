from django.conf import settings
from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Protect production login without making local development/tests brittle."""

    def allow_request(self, request, view):
        if not settings.IS_PRODUCTION:
            return True
        return super().allow_request(request, view)
