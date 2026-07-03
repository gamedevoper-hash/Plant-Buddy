from flask import Flask, render_template, request, jsonify, Response
from datetime import datetime, timedelta
import sqlite3
import bcrypt
import jwt
import json
from google import genai

app = Flask(__name__)
DB_NAME = "ultimate_paradise.db"
SECRET_KEY = "STRICT_CRYPTO_GARDEN_KEY_999"

# 🔴 ضع مفتاح Gemini الخاص بك هنا للتشغيل
GEMINI_API_KEY = "AQ.Ab8RN6Jv7owSzUpqmi7U-ntQwVB1bzgN-yBPLnIBxT4rqTwkQA"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            streak_points INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            interval_months INTEGER DEFAULT 0,
            interval_days INTEGER DEFAULT 0,
            interval_minutes INTEGER DEFAULT 0,
            next_water_time TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

def get_user_from_token(headers):
    token = headers.get('Authorization')
    if not token: return None
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return data['user_id']
    except:
        return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (data['username'], hashed_pw))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        token = jwt.encode({"user_id": user_id}, SECRET_KEY, algorithm="HS256")
        return jsonify({"token": token}), 201
    except:
        return jsonify({"error": "Username already exists"}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (data['username'],))
    user = cursor.fetchone()
    conn.close()
    if user and bcrypt.checkpw(data['password'].encode('utf-8'), user['password'].encode('utf-8')):
        token = jwt.encode({"user_id": user['id']}, SECRET_KEY, algorithm="HS256")
        return jsonify({"token": token}), 200
    return jsonify({"error": "Invalid login Credentials"}), 401

@app.route('/api/plants', methods=['GET'])
def get_plants():
    user_id = get_user_from_token(request.headers)
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plants WHERE user_id = ?", (user_id,))
    plants = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT streak_points FROM users WHERE id = ?", (user_id,))
    streak_points = cursor.fetchone()[0]
    conn.close()
    return jsonify({"plants": plants, "streak_points": streak_points})

@app.route('/api/plants', methods=['POST'])
def add_plant():
    user_id = get_user_from_token(request.headers)
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    
    total_days = (data['interval_months'] * 30) + data['interval_days']
    next_time = datetime.now() + timedelta(days=total_days, minutes=data['interval_minutes'])
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO plants (user_id, name, interval_months, interval_days, interval_minutes, next_water_time)
                      VALUES (?, ?, ?, ?, ?, ?)''', 
                   (user_id, data['name'], data['interval_months'], data['interval_days'], data['interval_minutes'], next_time.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"}), 201

@app.route('/api/plants/<int:plant_id>/water', methods=['POST'])
def water_plant(plant_id):
    user_id = get_user_from_token(request.headers)
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT interval_months, interval_days, interval_minutes, next_water_time FROM plants WHERE id = ? AND user_id = ?", (plant_id, user_id))
    row = cursor.fetchone()
    
    if row:
        # نظام مكافآت الجوائز والالتزام: لو تم الري في الوقت المحدد قبل انتهاء المؤشر، يُمنح نقاط التزام إضافية
        is_on_time = datetime.now() < datetime.strptime(row[3], '%Y-%m-%d %H:%M:%S')
        if is_on_time:
            cursor.execute("UPDATE users SET streak_points = streak_points + 10 WHERE id = ?", (user_id,))
        
        total_days = (row[0] * 30) + row[1]
        new_next = datetime.now() + timedelta(days=total_days, minutes=row[2])
        cursor.execute("UPDATE plants SET next_water_time = ? WHERE id = ?", (new_next.strftime('%Y-%m-%d %H:%M:%S'), plant_id))
        conn.commit()
        
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/plants/<int:plant_id>', methods=['DELETE'])
def delete_plant(plant_id):
    user_id = get_user_from_token(request.headers)
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plants WHERE id = ? AND user_id = ?", (plant_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# ⚡ محرك التوليد المتدفق السريع للغاية (Gemini Instant Streaming Engine)
@app.route('/api/ai/stream', methods=['POST'])
def ai_stream():
    user_id = get_user_from_token(request.headers)
    if not user_id: return Response("Unauthorized", status=401)
    user_msg = request.json.get('message')

    def generate_chunks():
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            # استدعاء خاصية البث المباشر المسرع للحصول على استجابة فورية بدون فترات انتظار معالجة
            response = client.models.generate_content_stream(
                model='gemini-2.5-flash',
                contents=f"أنت خبير الأسمدة وأمراض النباتات الذكي الفكاهي في تطبيق Plant Paradise. ساعد المستخدم باحترافية شديدة مع تلميحات فكاهية جادة ومباشرة جداً بخصوص سؤاله: {user_msg}"
            )
            for chunk in response:
                yield chunk.text
        except Exception as e:
            yield "تأكد من إرفاق مفتاح Gemini API Key الصحيح لتشغيل الاستجابة الحية المسرعة."

    return Response(generate_chunks(), mimetype='text/plain')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=7860)