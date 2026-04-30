import uuid
import os
from datetime import datetime, timedelta
from flask import Blueprint, url_for, render_template, abort
from flask_mail import Message
from extensions import mail, db
from models import Match, Donation

notifications_bp = Blueprint('notifications', __name__)

def generate_token():
    return str(uuid.uuid4())

def send_match_emails(blood_request, matched_donors):
    """Called after a request is raised. Sends email to each matched donor."""
    for donor in matched_donors:
        token = generate_token()

        # Save match record with token
        match = Match(
            request_id   = blood_request.id,
            donor_id     = donor['id'],
            status       = 'pending',
            token        = token,
            responded_at = None,
            distance_km  = round(donor['distance'], 2)
        )
        db.session.add(match)

        # Build email links
        yes_url = url_for('notifications.respond', token=token, action='yes', _external=True)
        no_url  = url_for('notifications.respond', token=token, action='no',  _external=True)

        html_body = render_template('email/match_email.html',
            donor_name     = donor['name'],
            blood_group    = blood_request.blood_group,
            units          = blood_request.units,
            hospital       = blood_request.hospital_name,
            urgency        = blood_request.urgency,
            yes_url        = yes_url,
            no_url         = no_url,
            expires_hours  = 48
        )

        msg = Message(
            subject    = f"[URGENT] Blood Request — {blood_request.blood_group} needed at {blood_request.hospital_name}",
            recipients = [donor['email']] if 'email' in donor else [], # Ensure donor email is passed
            html       = html_body
        )
        # Note: Sender is usually configured globally or set here
        try:
            if 'email' in donor and donor['email']:
                mail.send(msg)
        except Exception as e:
            print(f"Email failed for {donor.get('email')}: {e}")

    db.session.commit()

@notifications_bp.route('/respond/<token>/<action>')
def respond(token, action):
    match = Match.query.filter_by(token=token).first_or_404()

    # Check already responded
    if match.status != 'pending':
        return render_template('respond_done.html',
            message="You have already responded to this request.",
            status=match.status)

    match.status       = 'accepted' if action == 'yes' else 'declined'
    match.responded_at = datetime.utcnow()

    if action == 'yes':
        # Update donor's last donation date
        donation = Donation(
            donor_id   = match.donor_id,
            donated_on = datetime.utcnow().date(),
            place      = match.blood_request.hospital_name,
            blood_group= match.donor.blood_group,
            units      = 1.0
        )
        db.session.add(donation)

        # Check if 3rd donation milestone
        donation_count = Donation.query.filter_by(donor_id=match.donor_id).count() + 1
        if donation_count % 3 == 0:
            donation.certificate_issued = True
            
        match.donor.last_donation_date = datetime.utcnow().date().strftime('%Y-%m-%d')

    db.session.commit()

    return render_template('respond_done.html',
        message = "Thank you! The seeker has been notified." if action == 'yes'
                  else "Understood. We'll notify other donors.",
        status  = match.status)

def send_sms_twilio(phone, message):
    """Optional SMS via Twilio — skips gracefully if not configured."""
    sid   = os.environ.get('TWILIO_ACCOUNT_SID')
    token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_  = os.environ.get('TWILIO_FROM_NUMBER')
    if not all([sid, token, from_]):
        print("Twilio not configured — skipping SMS")
        return
    try:
        from twilio.rest import Client
        Client(sid, token).messages.create(body=message, from_=from_, to=phone)
    except Exception as e:
        print(f"SMS failed: {e}")
