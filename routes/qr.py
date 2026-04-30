"""QR Generation & Verification – signed JWT tokens, invalid tokens rejected."""
import os
import io
import json
import qrcode
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, send_file, jsonify, current_app, abort, url_for
from flask_login import login_required, current_user

try:
    import jwt as pyjwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

qr_bp = Blueprint('qr', __name__, url_prefix='/qr')

JWT_SECRET    = os.environ.get('JWT_SECRET_KEY', 'bloodconnect_qr_secret_2024')
JWT_ALGORITHM = 'HS256'
QR_EXPIRY_H   = 72  # QR valid for 72 hours


# ─── helpers ────────────────────────────────────────────────────────────────

def generate_qr_token(order) -> str:
    """Create a signed JWT payload for an Order and return the token string."""
    if not JWT_AVAILABLE:
        # Fallback: use a simple UUID-based token stored in order
        import uuid
        return str(uuid.uuid4())

    payload = {
        'order_id':    order.id,
        'user_id':     order.user_id,
        'hospital':    order.hospital_name,
        'blood_items': json.loads(order.items_json),
        'iat':         datetime.now(timezone.utc),
        'exp':         datetime.now(timezone.utc) + timedelta(hours=QR_EXPIRY_H),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_qr_token(token: str):
    """
    Verify a JWT token. Returns (payload_dict, None) on success,
    or (None, error_string) on failure.
    """
    if not JWT_AVAILABLE:
        return None, 'PyJWT library not installed.'

    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload, None
    except pyjwt.ExpiredSignatureError:
        return None, 'QR code has expired.'
    except pyjwt.InvalidTokenError as e:
        return None, f'Invalid token: {e}'


def _build_qr_image(token: str):
    """Generate a PIL QR image in-memory and return a BytesIO PNG."""
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    # Embed full verify URL so any QR scanner opens the verify page
    verify_url = f"{os.environ.get('BASE_URL', 'http://localhost:5000')}/qr/verify-page?token={token}"
    qr.add_data(verify_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color='#7f1d1d', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


# ─── routes ─────────────────────────────────────────────────────────────────

@qr_bp.route('/image/<int:order_id>')
@login_required
def qr_image(order_id):
    """Serve the QR code PNG for an order."""
    from models import Order
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)
    if not order.qr_token:
        abort(404)

    try:
        buf = _build_qr_image(order.qr_token)
        return send_file(buf, mimetype='image/png',
                         download_name=f'bloodconnect_qr_{order.id}.png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@qr_bp.route('/scan')
def scan_page():
    """Counter/hospital staff QR verification page."""
    token = request.args.get('token', '')
    return render_template('qr_verify.html', prefill_token=token)


@qr_bp.route('/verify-page')
def verify_page():
    """Auto-verify page when QR is scanned (opens via URL in QR)."""
    token = request.args.get('token', '')
    result = None
    if token:
        payload, error = verify_qr_token(token)
        if error:
            result = {'valid': False, 'error': error}
        else:
            from models import Order
            order = Order.query.get(payload.get('order_id'))
            result = {
                'valid':       True,
                'order_id':    payload.get('order_id'),
                'hospital':    payload.get('hospital'),
                'blood_items': payload.get('blood_items', []),
                'payment_status': order.payment_status if order else 'unknown',
                'user_name':   order.user.name if order else '—',
            }
    return render_template('qr_verify.html', prefill_token=token, result=result)


@qr_bp.route('/verify', methods=['POST'])
def verify_api():
    """
    JSON API: POST {token: '...'} → {valid, payload} or {valid: false, error}.
    Used by the counter app / JS frontend.
    """
    data  = request.get_json() or {}
    token = data.get('token', '').strip()

    if not token:
        return jsonify({'valid': False, 'error': 'No token provided.'}), 400

    payload, error = verify_qr_token(token)
    if error:
        return jsonify({'valid': False, 'error': error}), 400

    # Cross-check against DB
    from models import Order
    order = Order.query.get(payload.get('order_id'))
    if not order or order.qr_token != token:
        return jsonify({'valid': False, 'error': 'Token not found in database or already used.'}), 400

    return jsonify({
        'valid':          True,
        'order_id':       order.id,
        'hospital':       order.hospital_name,
        'blood_items':    json.loads(order.items_json),
        'payment_status': order.payment_status,
        'user_name':      order.user.name,
        'expires':        payload.get('exp'),
    })
