import threading
from django.utils.deprecation import MiddlewareMixin

_request_local = threading.local()

class AuditMiddleware(MiddlewareMixin):
    def process_request(self, request):
        _request_local.user = request.user
        _request_local.request = request
    
    def process_response(self, request, response):
        if hasattr(_request_local, 'user'):
            del _request_local.user
        if hasattr(_request_local, 'request'):
            del _request_local.request
        return response

def get_current_user():
    return getattr(_request_local, 'user', None)

def get_current_request():
    return getattr(_request_local, 'request', None)