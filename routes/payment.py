"""Payment Integration – clean Razorpay mock with status callbacks."""
import os
import json
import uuid
import hashlib
import hmac
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from extensions import db
from models import Order

payment_bp = Blueprint('payment', __name__, url_prefix='/payment')

# Mock Razorpay credentials (real keys would come from env)
RAZORPAY_KEY_ID     = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_MOCK_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'mock_secret_bloodconnect_2024')


def _generate_mock_order_id():
    return 'order_' + uuid.uuid4().hex[:16].upper()


def _generate_mock_payment_id():
    return 'pay_' + uuid.uuid4().hex[:14].upper()


def _generate_signature(order_id, payment_id, secret=RAZORPAY_KEY_SECRET):
    """Razorpay signature: HMAC-SHA256 of 'order_id|payment_id' with key secret."""
    msg = f"{order_id}|{payment_id}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


# ─── routes ────────────────────────────────────────────────────────────────

@payment_bp.route('/pay/<int:order_id>')
@login_required
def pay(order_id):
    """Show the Razorpay mock checkout page."""
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        from flask import abort; abort(403)
    if order.payment_status == 'paid':
        return redirect(url_for('cart.order_success', order_id=order.id))

    # Generate a mock Razorpay order_id
    mock_order_id = _generate_mock_order_id()
    session[f'mock_order_{order.id}'] = mock_order_id

    return render_template('payment.html',
        order       = order,
        razorpay_key= RAZORPAY_KEY_ID,
        mock_order_id = mock_order_id,
        amount_paise  = int(order.net_payable * 100),   # Razorpay uses paise
        items         = json.loads(order.items_json)
    )


@payment_bp.route('/initiate', methods=['POST'])
@login_required
def initiate():
    """API endpoint: create a mock Razorpay order JSON."""
    order_id = request.json.get('order_id')
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    mock_order_id = _generate_mock_order_id()
    session[f'mock_order_{order.id}'] = mock_order_id

    return jsonify({
        'id':       mock_order_id,
        'amount':   int(order.net_payable * 100),
        'currency': 'INR',
        'key':      RAZORPAY_KEY_ID
    })


@payment_bp.route('/verify', methods=['POST'])
@login_required
def verify():
    """Verify payment signature and mark order as paid."""
    data = request.get_json() or request.form

    order_db_id    = int(data.get('order_db_id', 0))
    razorpay_order = data.get('razorpay_order_id', '')
    razorpay_pay   = data.get('razorpay_payment_id', '')
    razorpay_sig   = data.get('razorpay_signature', '')
    simulate       = data.get('simulate')      # 'success' | 'failure'

    order = Order.query.get_or_404(order_db_id)
    if order.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    # ── MOCK path (simulate param set by JS) ──
    if simulate == 'failure':
        order.payment_status = 'failed'
        db.session.commit()
        return jsonify({'success': False, 'message': 'Payment declined (simulated).'})

    # For mock: generate a payment_id and skip real signature check
    if not razorpay_pay:
        razorpay_pay = _generate_mock_payment_id()

    expected_sig = _generate_signature(razorpay_order, razorpay_pay)

    # In mock mode, accept if signature matches OR if key is the test mock key
    if razorpay_sig == expected_sig or RAZORPAY_KEY_ID.startswith('rzp_test_MOCK'):
        _mark_paid(order, razorpay_pay)
        return jsonify({'success': True, 'redirect': url_for('cart.order_success', order_id=order.id)})

    order.payment_status = 'failed'
    db.session.commit()
    return jsonify({'success': False, 'message': 'Signature verification failed.'})


@payment_bp.route('/webhook', methods=['POST'])
def webhook():
    """Razorpay webhook stub – verifies X-Razorpay-Signature."""
    payload   = request.get_data()
    signature = request.headers.get('X-Razorpay-Signature', '')
    expected  = hmac.new(RAZORPAY_KEY_SECRET.encode(), payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return jsonify({'error': 'Invalid signature'}), 400

    event = request.json.get('event', '')
    if event == 'payment.captured':
        payment_id = request.json['payload']['payment']['entity']['id']
        order_rzp  = request.json['payload']['payment']['entity'].get('order_id')
        order = Order.query.filter(
            Order.payment_id == payment_id
        ).first()
        if order:
            _mark_paid(order, payment_id)

    return jsonify({'status': 'ok'})


@payment_bp.route('/success/<int:order_id>')
@login_required
def success(order_id):
    return redirect(url_for('cart.order_success', order_id=order_id))


@payment_bp.route('/failure')
@login_required
def failure():
    return render_template('payment_failure.html')


# ─── helpers ────────────────────────────────────────────────────────────────

def _mark_paid(order, payment_id):
    """Mark order paid, deduct wallet, clear session cart, generate QR token."""
    order.payment_status = 'paid'
    order.payment_id     = payment_id
    order.fulfilled_at   = datetime.utcnow()

    # Deduct wallet credit
    user = order.user
    user.wallet_balance  = max(0.0, user.wallet_balance - order.wallet_deducted)

    # Generate QR token (JWT) – imported lazily to avoid circular issues
    from routes.qr import generate_qr_token
    token = generate_qr_token(order)
    order.qr_token = token

    db.session.commit()

    # Clear cart from session if this was the pending order
    import flask
    if flask.session.get('pending_order_id') == order.id:
        flask.session.pop('cart', None)
        flask.session.pop('pending_order_id', None)
        flask.session.modified = True
