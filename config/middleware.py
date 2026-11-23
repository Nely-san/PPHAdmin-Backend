import uuid
import logging

logger = logging.getLogger(__name__)

class RequestIDMiddleware:
    """
    Middleware that assigns a unique request ID to each request.
    Extracts X-Request-ID header if provided, otherwise generates a UUID4.
    Attaches to request.id and sets X-Request-ID header on the response.
    Also logs uncaught 500 exceptions with request ID and full traceback.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get('X-Request-ID') or request.META.get('HTTP_X_REQUEST_ID')
        if not request_id:
            request_id = uuid.uuid4().hex

        request.id = request_id

        response = self.get_response(request)
        if response is not None:
            response['X-Request-ID'] = request.id
        return response

    def process_exception(self, request, exception):
        req_id = getattr(request, 'id', 'unknown')
        logger.error(
            f"500 Internal Server Error [Request ID: {req_id}] {request.method} {request.get_full_path()}: {exception}",
            exc_info=True,
            extra={'request': request}
        )
        return None
