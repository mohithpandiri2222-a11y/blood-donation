from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import atexit
from extensions import db, mail
from flask_mail import Message

scheduler = BackgroundScheduler(daemon=True)

def init_scheduler(app):
    """Call this inside your app factory after db.create_all()"""
    with app.app_context():
        scheduler.add_job(
            func     = lambda: check_shortage(app),
            trigger  = 'interval',
            hours    = 1,
            id       = 'shortage_check',
            replace_existing = True
        )
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown(wait=False))


def check_shortage(app):
    with app.app_context():
        from models import BloodRequest, Donation, User, Alert

        groups    = ['O-','O+','A-','A+','B-','B+','AB-','AB+']
        since     = datetime.utcnow() - timedelta(days=7)
        triggered = []

        for group in groups:
            req_count = BloodRequest.query.filter(
                BloodRequest.blood_group == group,
                BloodRequest.created_at  >= since,
                BloodRequest.status      == 'open'
            ).count()

            don_count = Donation.query.join(User).filter(
                User.blood_group    == group,
                Donation.donated_on >= since.date()
            ).count()

            # Trigger if requests > 2x donations OR requests > 3 with 0 donations
            if req_count > 0 and (don_count == 0 or req_count > 2 * don_count):
                # Avoid duplicate alerts within 24 hours
                recent = Alert.query.filter(
                    Alert.blood_group   == group,
                    Alert.triggered_at  >= datetime.utcnow() - timedelta(hours=24),
                    Alert.resolved      == False
                ).first()

                if not recent:
                    alert = Alert(
                        blood_group  = group,
                        triggered_at = datetime.utcnow(),
                        message      = (f"Shortage alert: {req_count} open requests "
                                        f"vs {don_count} donations in last 7 days."),
                        resolved     = False
                    )
                    db.session.add(alert)
                    triggered.append((group, req_count, don_count))

        db.session.commit()

        # Email admins if any alerts triggered
        if triggered:
            _email_admins_shortage(app, triggered)


def _email_admins_shortage(app, triggered):
    from models import User
    with app.app_context():
        admins = User.query.filter_by(role='admin').all()
        if not admins:
            return

        rows = "".join(
            f"<tr><td style='padding:8px;border:1px solid #eee;'>"
            f"<b style='color:#C0392B;'>{g}</b></td>"
            f"<td style='padding:8px;border:1px solid #eee;'>{r}</td>"
            f"<td style='padding:8px;border:1px solid #eee;'>{d}</td></tr>"
            for g, r, d in triggered
        )

        html = f"""
        <div style='font-family:Arial;max-width:500px;margin:auto;'>
          <div style='background:#C0392B;padding:20px;border-radius:8px 8px 0 0;'>
            <h2 style='color:#fff;margin:0;'>⚠️ Blood Shortage Alert</h2>
          </div>
          <div style='padding:24px;background:#fff;border:1px solid #eee;'>
            <p>The following blood groups have critical shortages (last 7 days):</p>
            <table style='width:100%;border-collapse:collapse;margin:16px 0;'>
              <tr style='background:#f9f9f9;'>
                <th style='padding:8px;border:1px solid #eee;text-align:left;'>Group</th>
                <th style='padding:8px;border:1px solid #eee;'>Open Requests</th>
                <th style='padding:8px;border:1px solid #eee;'>Donations</th>
              </tr>
              {rows}
            </table>
            <p style='color:#888;font-size:13px;'>
              Please take action to increase donor outreach for these groups.
            </p>
          </div>
        </div>"""

        for admin in admins:
            try:
                msg = Message(
                    subject    = "⚠️ Blood Shortage Alert — Immediate Action Needed",
                    recipients = [admin.email],
                    html       = html
                )
                mail.send(msg)
            except Exception as e:
                print(f"Admin alert email failed: {e}")
