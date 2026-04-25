# Automatic Absentee Alert System

A production-ready Flask web application for faculty attendance management, student attendance tracking, and automatic parent absence alerts through Twilio SMS and voice calls.

## Features

- Faculty and student login/signup with hashed passwords and Flask sessions
- SQLite relational schema for users, students, branches, classes, sections, and period-wise attendance
- 4 B.Tech years with A, B, and C sections plus seeded branch options
- Faculty dashboard with student management, branch/year/section filtering, attendance marking, reports, and alert logs
- Admin account controls for creating faculty logins and resetting faculty/student passwords
- Student dashboard with date-wise records, period-wise records, and overall attendance percentage
- Twilio SMS and text-to-speech voice call integration for absent students
- Responsive blue/white dashboard UI

## Run Locally

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Open `http://127.0.0.1:5000`.

Demo accounts:

- Faculty: `faculty` / `faculty123`
- Student: `student` / `student123`

The app creates `database.db` automatically on first run.

## Twilio Setup

Without Twilio credentials, the app runs in simulation mode and logs each SMS/call attempt in the database.

Set these environment variables for live delivery:

```bash
export FLASK_SECRET_KEY="09e4f9a73fe87b0ddf849c5b380f0415bae0f47f35fc93dfdf049a44d0755602"
export TWILIO_ACCOUNT_SID="ACe843519e5978d03c4e44232754e64b88"
export TWILIO_AUTH_TOKEN="b0e51eac52fb175e75fa938ccb364631"
export TWILIO_FROM_NUMBER="+18147040375"
export TWILIO_VOICE_FROM_NUMBER="+18147040375"
python3 app.py
```

When a student is marked `Absent`, the app sends:

- SMS: `Your son/daughter {name} (Roll No: {roll}) is absent to the college today on {date}.`
- Call: `Hello, your son or daughter {name} is absent to the college today.`

Use real, consented parent phone numbers in E.164 format.

## Deploy On Render

1. Push this project to GitHub.
2. Create a new Render Web Service.
3. Set the build command to `pip install -r requirements.txt`.
4. Set the start command to `gunicorn app:app`.
5. Add environment variables from `.env.example`.

## Deploy On Railway

1. Push this project to GitHub.
2. Create a Railway project from the repository.
3. Railway will use the included `Procfile`: `web: gunicorn app:app`.
4. Add environment variables from `.env.example`.

## Project Structure

```text
app.py
database.db
requirements.txt
Procfile
.env.example
templates/
  login.html
  dashboard.html
  students.html
  attendance.html
  accounts.html
  student_dashboard.html
static/
  style.css
```
