"""Wait-Time Predictor – innovative feature: estimates minutes until donor arrives."""
import math
from flask import Blueprint, jsonify, render_template
from flask_login import login_required
from extensions import db
from models import BloodRequest, Match, User, Donation
from datetime import date, timedelta

predictor_bp = Blueprint('predictor', __name__, url_prefix='/predict')

# ── Tuning constants ────────────────────────────────────────────────────────
SPEED_KM_PER_MIN   = 0.4     # ~24 km/h in city traffic
PREP_TIME_MIN      = 10.0    # donor gets ready / travel-to-clinic overhead
URGENCY_MULTIPLIER = {
    'critical': 0.7,   # donors rush for critical → faster
    'high':     0.85,
    'medium':   1.0,
    'low':      1.2,
}
RESPONSE_RATE_DEFAULT = 0.6   # 60% of notified donors typically respond


# ── helpers ─────────────────────────────────────────────────────────────────

def _donor_response_rate(blood_group: str) -> float:
    """
    Estimate response probability for a blood group based on historical donations.
    More donations in last 90 days → higher confidence.
    """
    since = date.today() - timedelta(days=90)
    recent_donors = db.session.query(User).join(
        Donation, Donation.donor_id == User.id
    ).filter(
        User.blood_group == blood_group,
        Donation.donated_on >= since
    ).count()

    # Logistic-style scaling: more recent active donors → higher rate (max 0.9)
    return min(0.9, RESPONSE_RATE_DEFAULT + recent_donors * 0.03)


def _predict_for_request(blood_request: BloodRequest) -> dict:
    """Core algorithm: return estimated wait time in minutes + metadata."""
    matches = Match.query.filter_by(request_id=blood_request.id).all()

    accepted = [m for m in matches if m.status == 'accepted']
    pending  = [m for m in matches if m.status == 'pending']

    # If already accepted, calculate ETA based on closest accepted donor distance
    if accepted:
        min_dist = min((m.distance_km or 5) for m in accepted)
        travel   = min_dist / SPEED_KM_PER_MIN
        urgency_mult = URGENCY_MULTIPLIER.get(blood_request.urgency, 1.0)
        eta_min  = round((PREP_TIME_MIN + travel) * urgency_mult, 1)
        confidence = 'high'
        status_msg = f'{len(accepted)} donor(s) confirmed — ETA ~{eta_min} min'
        return {
            'estimated_minutes': eta_min,
            'confidence':        confidence,
            'accepted_count':    len(accepted),
            'pending_count':     len(pending),
            'status':            status_msg,
            'factors':           {
                'closest_distance_km': round(min_dist, 2),
                'urgency':             blood_request.urgency,
                'travel_time_min':     round(travel, 1),
            }
        }

    # No acceptances yet: predict based on pending donors
    if pending:
        distances = [m.distance_km or 5 for m in pending]
        avg_dist   = sum(distances) / len(distances)
        travel     = avg_dist / SPEED_KM_PER_MIN
        urgency_mult = URGENCY_MULTIPLIER.get(blood_request.urgency, 1.0)
        resp_rate  = _donor_response_rate(blood_request.blood_group)

        # Waiting for response + travel
        response_wait = max(5, 30 * (1 - resp_rate))  # lower rate → longer wait
        eta_min = round((PREP_TIME_MIN + travel + response_wait) * urgency_mult, 1)
        confidence = 'medium'
        status_msg = f'{len(pending)} donor(s) notified — awaiting response'
        return {
            'estimated_minutes': eta_min,
            'confidence':        confidence,
            'accepted_count':    0,
            'pending_count':     len(pending),
            'status':            status_msg,
            'factors':           {
                'avg_distance_km':   round(avg_dist, 2),
                'urgency':           blood_request.urgency,
                'response_rate_pct': round(resp_rate * 100, 0),
                'response_wait_min': round(response_wait, 1),
            }
        }

    # No matches at all
    return {
        'estimated_minutes': None,
        'confidence':        'low',
        'accepted_count':    0,
        'pending_count':     0,
        'status':            'No donors matched yet — expanding search…',
        'factors':           {}
    }


# ── routes ──────────────────────────────────────────────────────────────────

@predictor_bp.route('/<int:request_id>')
def predict(request_id):
    """JSON endpoint: returns wait-time prediction for a blood request."""
    blood_request = BloodRequest.query.get_or_404(request_id)
    result = _predict_for_request(blood_request)
    result['request_id'] = request_id
    return jsonify(result)


@predictor_bp.route('/dashboard')
@login_required
def predictor_dashboard():
    """Quick overview of all open requests with predictions (for admins/demo)."""
    open_requests = BloodRequest.query.filter_by(status='open').order_by(
        BloodRequest.created_at.desc()
    ).limit(20).all()

    predictions = []
    for r in open_requests:
        pred = _predict_for_request(r)
        predictions.append({
            'request': r,
            'prediction': pred
        })

    return render_template('predictor_dashboard.html', predictions=predictions)
