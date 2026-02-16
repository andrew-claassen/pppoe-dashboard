import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, g, request

app = Flask(__name__)
DATABASE = "/opt/online/db/subscribers.db"

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# ------------------------------------------------------------------
# API endpoint: GET /api/subscribers
#
# Query parameters (all optional):
#   - router    : filter by router IP/name
#   - username  : filter by subscriber name
#   - framed_ip : filter by IP
#   - limit     : number of rows to return (default 100)
# ------------------------------------------------------------------
@app.route('/api/subscribers', methods=['GET'])
def get_subscribers():
    db = get_db()
    cursor = db.cursor()

    sql = "SELECT * FROM subscribers"
    params = []

    filters = []
    router = request.args.get('router')
    if router:
        filters.append("router = ?")
        params.append(router)

    username = request.args.get('username')
    if username:
        filters.append("username LIKE ?")
        params.append(f"%{username}%")

    framed_ip = request.args.get('framed_ip')
    if framed_ip:
        filters.append("framed_ip LIKE ?")
        params.append(f"%{framed_ip}%")

    if filters:
        sql += " WHERE " + " AND ".join(filters)

    # Pagination
    limit  = request.args.get('limit', 100, type=int)
    page   = request.args.get('page', 1, type=int)
    offset = (page - 1) * limit

    sql += f" LIMIT {limit} OFFSET {offset}"

    cursor.execute(sql, params)
    rows = [dict(row) for row in cursor.fetchall()]

    return jsonify(rows)

# Total session count and breakdown per router
@app.route('/api/summary', methods=['GET'])
def get_summary():
    db = get_db()
    cursor = db.cursor()

    # Get total count
    cursor.execute("SELECT COUNT(*) as total FROM subscribers")
    total = cursor.fetchone()['total']

    # Get count per router
    cursor.execute("""
        SELECT router, COUNT(*) as count
        FROM subscribers
        GROUP BY router
        ORDER BY router
    """)
    per_router = [dict(row) for row in cursor.fetchall()]

    return jsonify({
        'total': total,
        'per_router': per_router
    })

# Optional: health‑check endpoint
@app.route('/api/health', methods=['GET'])
def health():
    return "OK", 200

if __name__ == "__main__":
    # Expose port locally on host
    host = os.getenv('API_HOST', '127.0.0.1')
    port = int(os.getenv('API_PORT', 5000))
    app.run(host=host, port=port)
