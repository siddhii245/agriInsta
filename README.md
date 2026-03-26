
# AgriInsta - Extended (SQLite, password hashing, profile pics, likes/comments, pagination)

How to run (local):
1. Create a Python virtual environment and activate it.
2. Install requirements: `pip install -r requirements.txt`
3. Run: `python app.py`
4. Open http://127.0.0.1:5000 in your browser.

What's included:
- SQLite (Flask-SQLAlchemy) for durable storage.
- Password hashing with Flask-Bcrypt.
- Profile pictures (uploaded at registration or edit profile) saved to static/uploads/.
- Posts with optional images; likes and comments stored in DB.
- Pagination on home (5 posts per page) and search across titles, descriptions, and usernames.
- Simple form-based like/unlike and comment posting (redirects back).

Security notes:
- This is still a demo: use HTTPS, stronger secret key, input validation, rate limiting, and production static file serving in real deployments.
