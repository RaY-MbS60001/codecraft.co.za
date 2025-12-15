from functools import wraps
from flask import redirect, url_for, flash, jsonify, request
from flask_login import current_user
from datetime import datetime

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You need to be an admin to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def premium_required(f):
    """Decorator to require premium membership"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this feature.', 'warning')
            return redirect(url_for('login'))
        
        if not current_user.is_premium or (current_user.premium_expires and current_user.premium_expires <= datetime.now()):
            flash('This feature requires a premium membership.', 'warning')
            return redirect(url_for('upgrade_to_premium'))
        
        return f(*args, **kwargs)
    return decorated_function

def check_application_limit(f):
    """Decorator to check daily application limits"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        
        if not current_user.can_apply_today():
            if request.is_json:
                return jsonify({
                    'success': False, 
                    'message': 'Daily application limit reached. Upgrade to premium for unlimited applications!',
                    'upgrade_url': url_for('upgrade_to_premium'),
                    'remaining': current_user.get_remaining_applications()
                }), 429
            
            flash('Daily application limit reached (24 applications). Upgrade to premium for unlimited applications!', 'warning')
            return redirect(url_for('upgrade_to_premium'))
        
        return f(*args, **kwargs)
    return decorated_function

def track_application_usage(f):
    """Decorator to track application usage after successful application"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Execute the original function
        result = f(*args, **kwargs)
        
        # If the function executed successfully and user is authenticated
        if current_user.is_authenticated and result:
            # Check if it's a successful response (not an error redirect)
            if not isinstance(result, type(redirect('/'))):
                current_user.use_application()
        
        return result
    return decorated_function

def premium_feature_required(feature_name):
    """Decorator for specific premium features"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this feature.', 'warning')
                return redirect(url_for('login'))
            
            if not current_user.is_premium_active():
                flash(f'{feature_name} is a premium feature. Please upgrade your account.', 'warning')
                return redirect(url_for('upgrade_to_premium'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator