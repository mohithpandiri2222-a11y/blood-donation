from flask import Blueprint, render_template, abort, send_file, request
from flask_login import login_required, current_user
from models import db, User, Donation
from datetime import datetime, date, timedelta
from io import BytesIO
import json

health_card_bp = Blueprint('health_card', __name__)

def get_next_eligible_date(donations):
    if not donations:
        return date.today()
    last = max(d.donated_on for d in donations)
    return last + timedelta(days=90)

def get_eligibility_progress(donations):
    if not donations:
        return 100
    last = max(d.donated_on for d in donations)
    days_since = (date.today() - last).days
    return min(int((days_since / 90) * 100), 100)

def build_health_stats(donor, donations):
    total_units      = sum(d.units for d in donations)
    total_ml         = total_units * 450
    total_litres     = round(total_ml / 1000, 2)
    lives_impacted   = int(total_units * 3)
    next_eligible    = get_next_eligible_date(donations)
    days_until       = max((next_eligible - date.today()).days, 0)
    progress         = get_eligibility_progress(donations)
    is_eligible      = date.today() >= next_eligible
    streak           = compute_streak(donations)

    chart_labels = []
    chart_data   = []
    today = date.today()
    for i in range(11, -1, -1):
        month_start = date(today.year, today.month, 1) - timedelta(days=i*30)
        month_key   = month_start.strftime('%b %Y')
        count = sum(1 for d in donations if d.donated_on.year == month_start.year and d.donated_on.month == month_start.month)
        chart_labels.append(month_key)
        chart_data.append(count)

    return {
        'total_donations' : len(donations),
        'total_litres'    : total_litres,
        'total_ml'        : int(total_ml),
        'lives_impacted'  : lives_impacted,
        'next_eligible'   : next_eligible,
        'days_until'      : days_until,
        'progress'        : progress,
        'is_eligible'     : is_eligible,
        'streak'          : streak,
        'chart_labels'    : json.dumps(chart_labels),
        'chart_data'      : json.dumps(chart_data),
        'certificate_due' : len(donations) > 0 and len(donations) % 3 == 0,
    }

def compute_streak(donations):
    if not donations:
        return 0
    years = sorted(set(d.donated_on.year for d in donations), reverse=True)
    streak = 0
    current_year = date.today().year
    for y in years:
        if y == current_year - streak:
            streak += 1
        else:
            break
    return streak

@health_card_bp.route('/health-card')
@login_required
def my_health_card():
    if current_user.role != 'donor':
        abort(403)
    donations = Donation.query.filter_by(donor_id=current_user.id).order_by(Donation.donated_on.desc()).all()
    stats = build_health_stats(current_user, donations)
    return render_template('health_card.html', donor=current_user, donations=donations, stats=stats)

@health_card_bp.route('/health-card/<int:donor_id>/public')
def public_health_card(donor_id):
    donor = User.query.get_or_404(donor_id)
    if donor.role != 'donor':
        abort(404)
    donations = Donation.query.filter_by(donor_id=donor_id).order_by(Donation.donated_on.desc()).all()
    stats = build_health_stats(donor, donations)
    return render_template('health_card.html', donor=donor, donations=donations, stats=stats, is_public=True)

@health_card_bp.route('/health-card/pdf')
@login_required
def download_pdf():
    try:
        from weasyprint import HTML
    except ImportError:
        abort(500, "WeasyPrint not installed.")

    donations = Donation.query.filter_by(donor_id=current_user.id).order_by(Donation.donated_on.desc()).all()
    stats = build_health_stats(current_user, donations)
    html_content = render_template('health_card.html', donor=current_user, donations=donations, stats=stats, is_pdf=True)
    pdf_bytes = HTML(string=html_content, base_url=request.host_url).write_pdf()
    return send_file(BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=f'health_card_{current_user.name.replace(" ","_")}.pdf')

@health_card_bp.route('/certificate/<int:donor_id>')
@login_required
def certificate(donor_id):
    donor = User.query.get_or_404(donor_id)
    donations = Donation.query.filter_by(donor_id=donor_id).all()
    total_litres = round(sum(d.units for d in donations) * 0.45, 2)
    return render_template('certificate.html', donor=donor, donation_count=len(donations), total_litres=total_litres, lives=len(donations) * 3, issue_date=date.today().strftime('%d %B %Y'))
