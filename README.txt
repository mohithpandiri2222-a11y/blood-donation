========================================================
  BloodConnect – Blood Donation Management Portal
  Visakhapatnam, Andhra Pradesh, India
========================================================

OVERVIEW
--------
BloodConnect is a full-stack Flask web application that connects
blood donors, seekers, and blood banks to facilitate faster life-
saving decisions. It features smart donor matching using the
Haversine formula, real-time inventory tracking, and a Leaflet.js
interactive map.


FEATURES
--------
  • 3 User Roles    : Donor, Seeker, Blood Bank
  • Registration    : Role-specific forms with geo-location
  • Blood Groups    : All 8 ABO/Rh groups (O-, O+, A-, A+, B-, B+, AB-, AB+)
  • Compatibility   : Full ABO/Rh compatibility matrix
  • Matching Engine : Haversine distance ≤ 10 km, last donation > 90 days
  • Inventory       : Blood bank can set/update units per blood group
  • Public Page     : Live inventory visible without login
  • Map             : Leaflet.js pins for matched donors with popup info
  • Flash Alerts    : In-app notifications on match found
  • Seed Data       : 10 Visakhapatnam donors + 1 blood bank pre-loaded
  • Responsive UI   : Bootstrap 5, red/white medical theme


REQUIREMENTS
------------
  Python 3.9+
  Flask 3.x
  Werkzeug 3.x
  SQLite3 (built into Python)


QUICK START
-----------
  1. Install dependencies:
       pip install -r requirements.txt

  2. Run the application:
       python app.py

  3. Open your browser at:
       http://127.0.0.1:5000


DEMO ACCOUNTS (pre-seeded)
---------------------------
  Role        | Email                  | Password
  ------------|------------------------|-------------
  Donor       | arjun@example.com      | password123
  Donor       | priya@example.com      | password123
  Donor       | ravi@example.com       | password123
  Seeker      | seeker@example.com     | seeker123
  Blood Bank  | vizagbb@example.com    | bloodbank123


DATABASE SCHEMA
---------------
  users       – id, name, email, password(hash), role, phone,
                blood_group, lat, lng, last_donation_date

  donations   – id, donor_id, units, donation_date, notes

  requests    – id, seeker_id, blood_group, units, urgency, status, created_at

  matches     – id, request_id, donor_id, distance_km, status, matched_at

  inventory   – id, blood_bank_id, blood_group, units, updated_at


BLOOD COMPATIBILITY MATRIX
---------------------------
  Donor      Can donate to
  ---------  ---------------------------------------------------
  O-         All blood types (Universal Donor)
  O+         O+, A+, B+, AB+
  A-         A-, A+, AB-, AB+
  A+         A+, AB+
  B-         B-, B+, AB-, AB+
  B+         B+, AB+
  AB-        AB-, AB+
  AB+        AB+ only

  Recipient  Can receive from
  ---------  ---------------------------------------------------
  AB+        All blood types (Universal Recipient)
  AB-        O-, A-, B-, AB-
  A+         O-, O+, A-, A+
  A-         O-, A-
  B+         O-, O+, B-, B+
  B-         O-, B-
  O+         O-, O+
  O-         O- only


URL ROUTES
----------
  GET  /                        – Home page + live inventory summary
  GET  /inventory               – Public inventory page
  GET/POST /register            – New user registration
  GET/POST /login               – User login
  GET  /logout                  – Logout
  GET  /dashboard               – Role-specific dashboard
  GET/POST /donor/profile       – Edit donor profile
  POST /donor/log_donation      – Record a donation
  GET/POST /seeker/request      – Raise a blood request
  GET  /seeker/matches/<req_id> – View matched donors on map
  GET  /api/find_matches        – JSON API: nearby compatible donors
  GET/POST /bloodbank/inventory – Update blood bank inventory
  GET  /bloodbank/requests      – View all platform requests


PROJECT STRUCTURE
-----------------
  hackthon/
  ├── app.py                         ← Main Flask application
  ├── requirements.txt               ← Python dependencies
  ├── README.txt                     ← This file
  ├── blood_bank.db                  ← SQLite database (auto-created)
  └── templates/
      ├── base.html                  ← Base layout (navbar, footer, flash)
      ├── index.html                 ← Landing page
      ├── login.html                 ← Login form
      ├── register.html              ← Registration with role selector
      ├── dashboard.html             ← Role-specific dashboard
      ├── inventory.html             ← Public inventory view
      ├── donor_profile.html         ← Donor profile editor
      ├── seeker_request.html        ← Blood request form + live map
      ├── seeker_matches.html        ← Matched donors + Leaflet map
      ├── bloodbank_inventory.html   ← Blood bank stock management
      └── bloodbank_requests.html    ← All requests view


TECHNICAL NOTES
---------------
  • Passwords are hashed using Werkzeug's PBKDF2-SHA256
  • The database is auto-initialised on first run
  • Seed data is inserted only when the users table is empty
  • The matching engine uses the Haversine great-circle formula
  • Eligibility window: 90 days between donations
  • Match radius: 10 km
  • No email sending – notifications are in-app flash messages only
  • Leaflet.js tiles sourced from OpenStreetMap (free, no API key)


SEED DATA COORDINATES (Visakhapatnam)
--------------------------------------
  All 10 seeded donors are placed within the Visakhapatnam city
  area (~17.66–17.74 N, ~83.19–83.32 E). The default request
  location (17.6868, 83.2185) is near Dwaraka Nagar, VSP.


CONTRIBUTING
------------
  This project was built for a hackathon. Feel free to extend it
  with SMS alerts, appointment scheduling, or a mobile app.


LICENSE
-------
  MIT – Free to use and modify.

========================================================
  Emergency Helpline: 108  |  Blood Donation: 1910
========================================================
