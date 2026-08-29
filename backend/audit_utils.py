from flask import request
from flask_jwt_extended import get_jwt_identity, get_jwt
from models import db, AuditLog
from functools import wraps
import json

def log_audit(action, resource_type=None):
    """
    Decorator to log system actions to AuditLog.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                user_id = get_jwt_identity()
                jwt = get_jwt()
                actor_role = jwt.get('role', 'unknown')
            except Exception:
                user_id = None
                actor_role = 'unknown'

            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')

            resource_id = kwargs.get('id') or kwargs.get('order_id') or kwargs.get('user_id') or None

            response = f(*args, **kwargs)

            status_code = 200
            if isinstance(response, tuple) and len(response) > 1:
                status_code = response[1]
            elif hasattr(response, 'status_code'):
                status_code = response.status_code

            if 200 <= status_code < 400:
                audit = AuditLog(
                    actor_id=user_id,
                    actor_role=actor_role,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                try:
                    db.session.add(audit)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    import logging
                    logging.getLogger(__name__).error(f"Audit log failed: {e}")

            return response
        return wrapped
    return decorator

def manual_log_audit(action, resource_type=None, resource_id=None, old_value=None, new_value=None):
    """
    Function to manually log an audit record within a route.
    """
    try:
        user_id = get_jwt_identity()
        jwt = get_jwt()
        actor_role = jwt.get('role', 'unknown')
    except Exception:
        user_id = None
        actor_role = 'unknown'

    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr) if request else None
    user_agent = request.headers.get('User-Agent', '') if request else None

    if isinstance(old_value, dict) or isinstance(old_value, list):
        old_value = json.dumps(old_value)
    if isinstance(new_value, dict) or isinstance(new_value, list):
        new_value = json.dumps(new_value)

    audit = AuditLog(
        actor_id=user_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        ip_address=ip_address,
        user_agent=user_agent
    )
    try:
        db.session.add(audit)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        import logging
        logging.getLogger(__name__).error(f"Audit log failed: {e}")
