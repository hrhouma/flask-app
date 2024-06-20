import time
import psycopg2
from flask import Flask, Response, request, render_template, jsonify
import redis
from datetime import datetime
import hashlib
import os
import json

app = Flask(__name__)
startTime = datetime.now()

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
R_SERVER = redis.Redis(host=REDIS_HOST, port=6379)

max_retries = 10
for attempt in range(max_retries):
    try:
        db = psycopg2.connect(
            dbname=os.environ.get('POSTGRES_DB', 'userdb'),
            user=os.environ.get('POSTGRES_USER', 'eleve'),
            password=os.environ.get('POSTGRES_PASSWORD', 'password'),
            host=os.environ.get('POSTGRES_HOST', 'postgres')
        )
        break
    except psycopg2.OperationalError as e:
        print(f"Attempt {attempt + 1} of {max_retries} failed: {e}. Retrying in 5 seconds...")
        time.sleep(5)
else:
    print("All attempts to connect to PostgreSQL failed.")
    exit(1)

cursor = db.cursor()

@app.route('/')
def home():
    return "Welcome to the User Management Service"

@app.route('/add_user')
def add_user_form():
    return render_template('add_user.html')

@app.route('/init')
def init():
    try:
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("CREATE TABLE users (ID serial PRIMARY KEY, username varchar(30))")
        db.commit()
        return "DB Init done"
    except Exception as e:
        db.rollback()
        return str(e), 500

@app.route("/users/add", methods=['POST'])
def add_users():
    if request.is_json:
        req_json = request.get_json()
        user = req_json.get('user')
    else:
        user = request.form.get('user')

    if user:
        try:
            cursor.execute("INSERT INTO users (username) VALUES (%s)", (user,))
            db.commit()
            return jsonify({"message": "Added"}), 200
        except Exception as e:
            db.rollback()
            return str(e), 500
    else:
        return jsonify({"message": "User is required"}), 400

@app.route('/users/<uid>')
def get_users(uid):
    hash = hashlib.sha224(str(uid).encode('utf-8')).hexdigest()
    key = "sql_cache:" + hash

    if R_SERVER.get(key):
        return R_SERVER.get(key).decode("utf-8") + "(c)"
    else:
        try:
            cursor.execute("SELECT username FROM users WHERE ID = %s", (uid,))
            data = cursor.fetchone()
            if data:
                R_SERVER.set(key, data[0])
                R_SERVER.expire(key, 36)
                return R_SERVER.get(key).decode("utf-8")
            else:
                return "Record not found"
        except Exception as e:
            return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

