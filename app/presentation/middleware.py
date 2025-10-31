"""Custom middleware for security, logging, and request processing."""

import time
import logging
import uuid
from typing import Callable, Dict, Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""
    
    def __init__(self, app: ASGIApp, logger_name: str = "api.requests"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        # Generate correlation ID for request tracing
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        # Log request start
        start_time = time.time()
        self.logger.info(
            f"[{correlation_id}] {request.method} {request.url.path} - START",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown"),
            }
        )
        
        try:
            response = await call_next(request)
            
            # Log response
            process_time = time.time() - start_time
            self.logger.info(
                f"[{correlation_id}] {request.method} {request.url.path} - "
                f"{response.status_code} - {process_time:.3f}s",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": process_time,
                }
            )
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
            
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            self.logger.error(
                f"[{correlation_id}] {request.method} {request.url.path} - "
                f"ERROR - {process_time:.3f}s - {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "process_time": process_time,
                },
                exc_info=True
            )
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "correlation_id": correlation_id,
                },
                headers={"X-Correlation-ID": correlation_id}
            )


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for basic security headers and validation."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.blocked_paths = {"/admin", "/internal"}
        # More reasonable rate limits for production
        self.rate_limit_paths = {
            "/api/v1/tasks": 100,  # Allow 100 task requests per minute
            "/api/v1/tasks/{id}/agents": 50,  # 50 agent requests per minute
            "/health": 200,  # High limit for health checks
        }
        self.request_counts: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with security checks."""
        
        # Block access to internal paths
        if any(request.url.path.startswith(path) for path in self.blocked_paths):
            return JSONResponse(
                status_code=403,
                content={"error": "Forbidden"},
            )
        
        # Basic rate limiting (in-memory, simple implementation)
        client_ip = request.client.host if request.client else "unknown"
        if self._is_rate_limited(request.url.path, client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests"},
                headers={"Retry-After": "60"}
            )
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response
    
    def _is_rate_limited(self, path: str, client_ip: str) -> bool:
        """Simple in-memory rate limiting."""
        current_time = time.time()
        
        # Find matching rate limit path
        rate_limit = None
        for limit_path, limit_count in self.rate_limit_paths.items():
            if path.startswith(limit_path):
                rate_limit = limit_count
                break
        
        if not rate_limit:
            return False
        
        # Initialize tracking for this IP
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = {}
        
        # Clean old entries (older than 1 minute)
        minute_ago = current_time - 60
        self.request_counts[client_ip] = {
            timestamp: count for timestamp, count in self.request_counts[client_ip].items()
            if float(timestamp) > minute_ago
        }
        
        # Count requests in the last minute
        total_requests = sum(self.request_counts[client_ip].values())
        
        if total_requests >= rate_limit:
            return True
        
        # Record this request
        timestamp_key = str(int(current_time))
        self.request_counts[client_ip][timestamp_key] = \
            self.request_counts[client_ip].get(timestamp_key, 0) + 1
        
        return False


class CompressionMiddleware(BaseHTTPMiddleware):
    """Middleware for response compression."""
    
    def __init__(self, app: ASGIApp, minimum_size: int = 500):
        super().__init__(app)
        self.minimum_size = minimum_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with compression support."""
        response = await call_next(request)
        
        # Add compression headers if response is large enough
        if hasattr(response, 'body') and len(response.body) > self.minimum_size:
            accept_encoding = request.headers.get('accept-encoding', '')
            if 'gzip' in accept_encoding.lower():
                response.headers['Content-Encoding'] = 'gzip'
        
        return response


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Middleware for API versioning."""
    
    def __init__(self, app: ASGIApp, current_version: str = "v1"):
        super().__init__(app)
        self.current_version = current_version
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with API version handling."""
        # Add API version to request state
        request.state.api_version = self.current_version
        
        response = await call_next(request)
        
        # Add API version to response headers
        response.headers["X-API-Version"] = self.current_version
        
        return response
