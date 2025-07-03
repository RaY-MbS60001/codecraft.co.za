# security_middleware.py
from flask import Flask

def add_security_headers(app: Flask):
    @app.after_request
    def _add_security_headers(response):
        security_headers = {
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'SAMEORIGIN',
            'Content-Security-Policy': "default-src 'self'",
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'X-XSS-Protection': '1; mode=block'
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response
    
    return app