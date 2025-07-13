import os
import fitz  # PyMuPDF
import requests
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)

documents = {}

# 🔑 OpenRouter API Key & Headers
OPENROUTER_API_KEY = "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"
headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://campusconnect.replit.app",
    "X-Title": "CampusConnect AI"
}

# 🔧 Init DB
def init_db():
    conn = sqlite3.connect('campusconnect.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            student_id TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS calendar_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            time TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

init_db()

@app.route('/')
def serve_interface():
    return send_from_directory('.', 'index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = "".join([page.get_text() for page in doc])
        documents["testuser@example.com"] = text
        return jsonify({"extracted_text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    pdf_text = documents.get("testuser@example.com", "").strip()

    general_keywords = ["define", "what is", "who is", "where", "explain", "hello", "hi", "let's talk", "noun", "meaning", "example", "something else"]
    is_general = any(kw in user_message.lower() for kw in general_keywords)

    if is_general or not pdf_text:
        prompt = f"You are a helpful AI assistant for students. Answer clearly.\n\nUser: {user_message}\nAI:"
    else:
        prompt = f"You are a smart AI assistant based on the PDF below:\n\nPDF Notes:\n{pdf_text}\n\nUser: {user_message}\nAI:"

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        reply = response.json()["choices"][0]["message"]["content"]

        conn = sqlite3.connect('campusconnect.db')
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (email, question, answer) VALUES (?, ?, ?)",
                  ("testuser@example.com", user_message, reply))
        conn.commit()
        conn.close()

        return jsonify({"response": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/speak', methods=['POST'])
def speak():
    data = request.get_json()
    voice_text = data.get("voice", "").strip()

    prompt = f"You are a friendly AI tutor. Respond to this voice question:\n\n{voice_text}"

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        reply = response.json()["choices"][0]["message"]["content"]

        conn = sqlite3.connect('campusconnect.db')
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (email, question, answer) VALUES (?, ?, ?)",
                  ("testuser@example.com", voice_text, reply))
        conn.commit()
        conn.close()

        return jsonify({"response": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/calendar-entry', methods=['POST'])
def calendar_entry():
    data = request.get_json()
    voice_text = data.get("voice", "").strip()

    prompt = f"""
You are a smart AI assistant. Extract only the title and time from this calendar voice command.

Voice Command: "{voice_text}"

Reply format strictly as JSON:
{{"title": "...", "time": "..."}}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        content = response.json()["choices"][0]["message"]["content"]

        parsed = eval(content) if isinstance(content, str) else content
        title = parsed.get("title", "")
        time = parsed.get("time", "")

        conn = sqlite3.connect('campusconnect.db')
        c = conn.cursor()
        c.execute("INSERT INTO calendar_requests (title, time) VALUES (?, ?)", (title, time))
        conn.commit()
        conn.close()

        return jsonify({"message": "Calendar event saved ✅", "title": title, "time": time})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/calendar-requests', methods=['GET'])
def get_calendar_requests():
    conn = sqlite3.connect('campusconnect.db')
    c = conn.cursor()
    c.execute("SELECT title, time, created_at FROM calendar_requests ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify([
        {"title": r[0], "time": r[1], "created_at": r[2]} for r in rows
    ])

@app.route('/chat-history', methods=['GET'])
def chat_history():
    conn = sqlite3.connect('campusconnect.db')
    c = conn.cursor()
    c.execute("SELECT question, answer, timestamp FROM chat_history WHERE email = ? ORDER BY timestamp DESC",
              ("testuser@example.com",))
    chats = c.fetchall()
    conn.close()
    return jsonify([
        {"question": row[0], "answer": row[1], "timestamp": row[2]} for row in chats
    ])

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    student_id = data.get('student_id')
    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

    try:
        conn = sqlite3.connect('campusconnect.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (email, password, name, student_id) VALUES (?, ?, ?, ?)",
                  (email, hashed_pw, name, student_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Registration successful 🎉'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'User already exists'}), 400

@app.route('/login', methods=['POST'])
def login():
    return jsonify({'message': 'Login successful 🎉'})

@app.route('/campus-map', methods=['GET'])
def campus_map():
    buildings = [
        {"name": "Admin Block", "lat": 5.560013, "lon": -0.205503},
        {"name": "Computer Science Dept", "lat": 5.560442, "lon": -0.206212},
        {"name": "Library", "lat": 5.561092, "lon": -0.204912},
        {"name": "Engineering Workshop", "lat": 5.559823, "lon": -0.207501}
    ]
    return jsonify(buildings)

@app.route('/food-info', methods=['POST'])
def food_info():
    data = request.get_json()
    food_name = data.get("food", "").strip()

    if not food_name:
        return jsonify({"error": "No food name provided"}), 400

    prompt = f"""
You are a certified AI nutritionist. DO NOT give recipes or cooking instructions.

Only return:
- Health benefits of eating {food_name}
- Nutrients (e.g. carbs, proteins, vitamins)
- Energy level (calories or kcal)
- Effects on the body (e.g. improves digestion, boosts energy, etc.)

FOOD: {food_name}
"""

    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        reply = response.json()["choices"][0]["message"]["content"]
        return jsonify({"benefits": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
