import threading

_thread_locals = threading.local()

def get_current_request():
    return getattr(_thread_locals, 'request', None)

def get_current_user():
    req = get_current_request()
    if req and hasattr(req, 'user') and req.user is not None:
        return req.user
    return getattr(_thread_locals, 'user', None)

def get_current_username():
    user = get_current_user()
    if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
        return getattr(user, 'username', str(user))
    return 'SYSTEM'

class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        _thread_locals.user = getattr(request, 'user', None)
        try:
            response = self.get_response(request)
        finally:
            _thread_locals.request = None
            _thread_locals.user = None
        return response
