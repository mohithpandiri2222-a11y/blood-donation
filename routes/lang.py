from flask import Blueprint, session, redirect, request as req

lang_bp = Blueprint('lang', __name__)

TRANSLATIONS = {
    'en': {
        'nav_home':      'Home',
        'nav_register':  'Register',
        'nav_login':     'Login',
        'nav_directory': 'Find Donors',
        'nav_inventory': 'Blood Banks',
        'nav_request':   'Request Blood',
        'btn_donate':    'Become a Donor',
        'btn_request':   'Request Blood Now',
        'lbl_name':      'Full Name',
        'lbl_email':     'Email Address',
        'lbl_phone':     'Phone Number',
        'lbl_bloodgroup':'Blood Group',
        'lbl_location':  'Location',
        'status_open':   'Open',
        'status_fulfilled':'Fulfilled',
        'status_critical':'Critical',
        'status_medium': 'Medium',
        'status_low':    'Low',
        'msg_eligible':  'You are eligible to donate!',
        'msg_waiting':   'days until eligible',
    },
    'te': {
        'nav_home':      'హోమ్',
        'nav_register':  'నమోదు చేయండి',
        'nav_login':     'లాగిన్',
        'nav_directory': 'దాతలను కనుగొనండి',
        'nav_inventory': 'రక్తం బ్యాంకులు',
        'nav_request':   'రక్తం అభ్యర్థించండి',
        'btn_donate':    'దాత అవ్వండి',
        'btn_request':   'ఇప్పుడే రక్తం అభ్యర్థించండి',
        'lbl_name':      'పూర్తి పేరు',
        'lbl_email':     'ఇమెయిల్ చిరునామా',
        'lbl_phone':     'ఫోన్ నంబర్',
        'lbl_bloodgroup':'రక్త సమూహం',
        'lbl_location':  'స్థానం',
        'status_open':   'తెరుచుకుంది',
        'status_fulfilled':'నెరవేరింది',
        'status_critical':'అత్యవసర',
        'status_medium': 'మధ్యస్థం',
        'status_low':    'తక్కువ',
        'msg_eligible':  'మీరు రక్తదానం చేయడానికి అర్హులు!',
        'msg_waiting':   'రోజులు మిగిలి ఉన్నాయి',
    },
    'hi': {
        'nav_home':      'होम',
        'nav_register':  'पंजीकरण',
        'nav_login':     'लॉगिन',
        'nav_directory': 'डोनर खोजें',
        'nav_inventory': 'ब्लड बैंक',
        'nav_request':   'रक्त की मांग',
        'btn_donate':    'डोनर बनें',
        'btn_request':   'अभी रक्त मांगें',
        'lbl_name':      'पूरा नाम',
        'lbl_email':     'ईमेल पता',
        'lbl_phone':     'फ़ोन नंबर',
        'lbl_bloodgroup':'रक्त समूह',
        'lbl_location':  'स्थान',
        'status_open':   'खुला',
        'status_fulfilled':'पूर्ण',
        'status_critical':'आपातकाल',
        'status_medium': 'मध्यम',
        'status_low':    'कम',
        'msg_eligible':  'आप रक्तदान के योग्य हैं!',
        'msg_waiting':   'दिन बाकी हैं',
    }
}

@lang_bp.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(req.referrer or '/')

def get_t():
    """Returns translation dict for current language."""
    lang = session.get('lang', 'en')
    return TRANSLATIONS.get(lang, TRANSLATIONS['en'])
