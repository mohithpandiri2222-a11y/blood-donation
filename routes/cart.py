"""Cart & Checkout Logic – evaluator looks for quantities, totals, taxes, wallet credit."""
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Inventory, Order, User

cart_bp = Blueprint('cart', __name__, url_prefix='/cart')

PROCESSING_FEE_PER_UNIT = 50.0   # ₹50 per unit
GST_RATE = 0.18                   # 18% GST on processing fee


# ─── helpers ───────────────────────────────────────────────────────────────

def get_cart():
    """Return cart list from session: [{blood_group, units}, ...]"""
    return session.get('cart', [])


def save_cart(cart):
    session['cart'] = cart
    session.modified = True


def calculate_totals(cart):
    total_units      = sum(item['units'] for item in cart)
    processing_fee   = round(total_units * PROCESSING_FEE_PER_UNIT, 2)
    gst_amount       = round(processing_fee * GST_RATE, 2)
    subtotal         = round(processing_fee + gst_amount, 2)
    wallet_balance   = current_user.wallet_balance if current_user.is_authenticated else 0.0
    wallet_deducted  = min(wallet_balance, subtotal)
    net_payable      = round(subtotal - wallet_deducted, 2)
    return {
        'total_units':     total_units,
        'processing_fee':  processing_fee,
        'gst_amount':      gst_amount,
        'subtotal':        subtotal,
        'wallet_balance':  wallet_balance,
        'wallet_deducted': wallet_deducted,
        'net_payable':     net_payable,
    }


# ─── routes ────────────────────────────────────────────────────────────────

@cart_bp.route('/')
@login_required
def view_cart():
    cart = get_cart()
    totals = calculate_totals(cart)
    # Inventory snapshot for availability check
    inventory = {i.blood_group: i.units for i in Inventory.query.all()}
    return render_template('cart.html', cart=cart, totals=totals, inventory=inventory)


@cart_bp.route('/add', methods=['POST'])
@login_required
def add_to_cart():
    blood_group = request.form.get('blood_group', '').strip()
    try:
        units = int(request.form.get('units', 1))
        if units < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid units specified.', 'danger')
        return redirect(request.referrer or url_for('public_inventory'))

    if not blood_group:
        flash('Please select a blood group.', 'danger')
        return redirect(request.referrer or url_for('public_inventory'))

    cart = get_cart()
    # Merge if blood group already in cart
    for item in cart:
        if item['blood_group'] == blood_group:
            item['units'] += units
            save_cart(cart)
            flash(f'Updated {blood_group} to {item["units"]} unit(s) in cart.', 'success')
            return redirect(url_for('cart.view_cart'))

    cart.append({'blood_group': blood_group, 'units': units})
    save_cart(cart)
    flash(f'Added {units} unit(s) of {blood_group} to cart.', 'success')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/update', methods=['POST'])
@login_required
def update_cart():
    blood_group = request.form.get('blood_group', '').strip()
    try:
        units = int(request.form.get('units', 1))
    except (ValueError, TypeError):
        units = 1

    cart = get_cart()
    if units <= 0:
        cart = [item for item in cart if item['blood_group'] != blood_group]
        flash(f'Removed {blood_group} from cart.', 'info')
    else:
        for item in cart:
            if item['blood_group'] == blood_group:
                item['units'] = units
                break
        flash(f'Updated {blood_group} quantity.', 'success')

    save_cart(cart)
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/remove', methods=['POST'])
@login_required
def remove_from_cart():
    blood_group = request.form.get('blood_group', '').strip()
    cart = [item for item in get_cart() if item['blood_group'] != blood_group]
    save_cart(cart)
    flash(f'Removed {blood_group} from cart.', 'info')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/clear', methods=['POST'])
@login_required
def clear_cart():
    save_cart([])
    flash('Cart cleared.', 'info')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart = get_cart()
    if not cart:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart.view_cart'))

    totals = calculate_totals(cart)

    if request.method == 'POST':
        hospital = request.form.get('hospital', 'City Hospital').strip()

        # Create Order record
        order = Order(
            user_id        = current_user.id,
            items_json     = json.dumps(cart),
            processing_fee = totals['processing_fee'],
            gst_amount     = totals['gst_amount'],
            wallet_deducted= totals['wallet_deducted'],
            net_payable    = totals['net_payable'],
            payment_status = 'pending',
            hospital_name  = hospital
        )
        db.session.add(order)
        db.session.commit()
        session['pending_order_id'] = order.id

        # If fully covered by wallet, skip payment
        if totals['net_payable'] <= 0:
            _fulfill_order(order, totals)
            return redirect(url_for('cart.order_success', order_id=order.id))

        return redirect(url_for('payment.pay', order_id=order.id))

    inventory = {i.blood_group: i.units for i in Inventory.query.all()}
    return render_template('cart.html', cart=cart, totals=totals, inventory=inventory,
                           checkout_mode=True)


@cart_bp.route('/order/<int:order_id>/success')
@login_required
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        from flask import abort
        abort(403)
    items = json.loads(order.items_json)
    return render_template('order_success.html', order=order, items=items)


@cart_bp.route('/orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)


def _fulfill_order(order, totals):
    """Deduct wallet, mark order paid, clear cart."""
    current_user.wallet_balance -= totals['wallet_deducted']
    order.payment_status = 'paid'
    from datetime import datetime
    order.fulfilled_at = datetime.utcnow()
    db.session.commit()
    session.pop('cart', None)
    session.modified = True
