from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_session import Session
import sqlite3
import os
import math
import bcrypt
from datetime import datetime

app = Flask(__name__)

# Cấu hình Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'your-secret-key-here'
Session(app)

DB_PATH = os.path.join("Data", "MangaZekdb.db")

# Tạo bảng users, reading_history, favorites, và user_levels nếu chưa tồn tại
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            manga_id TEXT,
            chapter_id TEXT,
            read_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            manga_id TEXT,
            added_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            level INTEGER,
            chapter_count INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# Khởi tạo database
init_db()

# Trang chủ - Hiển thị danh sách truyện với phân trang
@app.route('/')
def index():
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 12
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = "SELECT id, title, cover_url FROM manga"
    params = []
    if search_query:
        query += " WHERE title LIKE ?"
        params.append(f'%{search_query}%')
    cursor.execute(query, params)
    total_manga = cursor.fetchall()
    total_pages = math.ceil(len(total_manga) / per_page)
    offset = (page - 1) * per_page
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    manga_list = cursor.fetchall()
    conn.close()
    return render_template('index.html', manga_list=manga_list, search_query=search_query, page=page, total_pages=total_pages)

# Trang đăng ký
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            return render_template('register.html', error="Vui lòng nhập đầy đủ email và mật khẩu.")
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error="Email đã tồn tại.")
        finally:
            conn.close()
    return render_template('register.html', error=None)

# Trang đăng nhập
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            return render_template('login.html', error="Vui lòng nhập đầy đủ email và mật khẩu.")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2]):
            session['user_id'] = user[0]
            session['email'] = user[1]
            return redirect(url_for('index'))
        return render_template('login.html', error="Email hoặc mật khẩu không đúng.")
    return render_template('login.html', error=None)

# Đăng xuất
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('email', None)
    return redirect(url_for('index'))

# Trang thông tin người dùng
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Lấy lịch sử đọc (bao gồm cover_url)
    cursor.execute('''
        SELECT rh.manga_id, rh.chapter_id, rh.read_at, m.title, m.cover_url
        FROM reading_history rh
        JOIN manga m ON rh.manga_id = m.id
        WHERE rh.user_id = ?
        ORDER BY rh.read_at DESC
        LIMIT 10
    ''', (session['user_id'],))
    reading_history = cursor.fetchall()
    
    # Lấy danh sách truyện yêu thích
    cursor.execute('''
        SELECT f.manga_id, f.added_at, m.title, m.cover_url
        FROM favorites f
        JOIN manga m ON f.manga_id = m.id
        WHERE f.user_id = ?
        ORDER BY f.added_at DESC
    ''', (session['user_id'],))
    favorites = cursor.fetchall()
    
    # Lấy cấp độ người dùng
    cursor.execute("SELECT level, chapter_count FROM user_levels WHERE user_id = ?", (session['user_id'],))
    user_level = cursor.fetchone()
    if not user_level:
        # Nếu chưa có, khởi tạo cấp độ
        cursor.execute("SELECT COUNT(*) FROM reading_history WHERE user_id = ?", (session['user_id'],))
        chapter_count = cursor.fetchone()[0]
        level = chapter_count // 10
        cursor.execute("INSERT INTO user_levels (user_id, level, chapter_count) VALUES (?, ?, ?)", (session['user_id'], level, chapter_count))
        conn.commit()
        user_level = (level, chapter_count)
    
    conn.close()
    return render_template('profile.html', reading_history=reading_history, favorites=favorites, user_level=user_level)

# Thêm truyện vào danh sách yêu thích
@app.route('/favorite/<manga_id>', methods=['POST'])
def add_favorite(manga_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM favorites WHERE user_id = ? AND manga_id = ?", (session['user_id'], manga_id))
    if cursor.fetchone():
        conn.close()
        return redirect(url_for('manga_detail', manga_id=manga_id))
    
    added_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("INSERT INTO favorites (user_id, manga_id, added_at) VALUES (?, ?, ?)", (session['user_id'], manga_id, added_at))
    conn.commit()
    conn.close()
    return redirect(url_for('manga_detail', manga_id=manga_id))

# Xóa truyện khỏi danh sách yêu thích
@app.route('/unfavorite/<manga_id>', methods=['POST'])
def remove_favorite(manga_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM favorites WHERE user_id = ? AND manga_id = ?", (session['user_id'], manga_id))
    conn.commit()
    conn.close()
    return redirect(url_for('manga_detail', manga_id=manga_id))

# Trang chi tiết truyện
@app.route('/manga/<manga_id>')
def manga_detail(manga_id):
    if 'user_id' in session:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM favorites WHERE user_id = ? AND manga_id = ?", (session['user_id'], manga_id))
        is_favorited = cursor.fetchone() is not None
        conn.close()
    else:
        is_favorited = False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM manga WHERE id = ?", (manga_id,))
    manga = cursor.fetchone()
    cursor.execute("SELECT * FROM chapter WHERE manga_id = ?", (manga_id,))
    chapters = cursor.fetchall()
    conn.close()
    return render_template('manga_detail.html', manga=manga, chapters=chapters, is_favorited=is_favorited)

# Trang đọc truyện
@app.route('/read/<manga_id>/<chapter_id>')
def read_manga(manga_id, chapter_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chapter WHERE id = ?", (chapter_id,))
    chapter = cursor.fetchone()
    images = chapter[3].split('\n') if chapter and chapter[3] else []
    
    # Lưu lịch sử đọc nếu người dùng đã đăng nhập
    if 'user_id' in session:
        read_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO reading_history (user_id, manga_id, chapter_id, read_at) VALUES (?, ?, ?, ?)", 
                      (session['user_id'], manga_id, chapter_id, read_at))
        # Cập nhật cấp độ người dùng
        cursor.execute("SELECT COUNT(*) FROM reading_history WHERE user_id = ?", (session['user_id'],))
        chapter_count = cursor.fetchone()[0]
        level = chapter_count // 10
        cursor.execute("INSERT OR REPLACE INTO user_levels (id, user_id, level, chapter_count) VALUES ((SELECT id FROM user_levels WHERE user_id = ?), ?, ?, ?)", 
                      (session['user_id'], session['user_id'], level, chapter_count))
        conn.commit()
    
    cursor.execute("SELECT id, title FROM chapter WHERE manga_id = ? ORDER BY id", (manga_id,))
    all_chapters = cursor.fetchall()
    current_index = next((i for i, c in enumerate(all_chapters) if c[0] == chapter_id), -1)
    prev_chapter = all_chapters[current_index - 1][0] if current_index > 0 else None
    next_chapter = all_chapters[current_index + 1][0] if current_index < len(all_chapters) - 1 else None
    chapters_list = [(chap[0], f"Chapter {i + 1}: {chap[1]}" if chap[1] else f"Chapter {i + 1}") for i, chap in enumerate(all_chapters)]
    
    conn.close()
    return render_template('read.html', manga_id=manga_id, chapter_id=chapter_id, images=images, prev_chapter=prev_chapter, next_chapter=next_chapter, chapters_list=chapters_list)

# Tìm kiếm theo thể loại hoặc tác giả
@app.route('/filter/<filter_type>/<value>')
def filter_manga(filter_type, value):
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Số truyện trên mỗi trang
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Đếm tổng số truyện phù hợp
    if filter_type == "genre":
        query = "SELECT id, title, cover_url FROM manga WHERE genres LIKE ?"
        params = [f'%{value}%']
    elif filter_type == "author":
        query = "SELECT id, title, cover_url FROM manga WHERE authors LIKE ?"
        params = [f'%{value}%']
    else:
        return render_template('index.html', manga_list=[], filter_type=filter_type, filter_value=value, page=1, total_pages=1)
    
    cursor.execute(query, params)
    total_manga = cursor.fetchall()
    total_pages = math.ceil(len(total_manga) / per_page)
    
    # Lấy danh sách truyện cho trang hiện tại
    offset = (page - 1) * per_page
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    manga_list = cursor.fetchall()
    
    conn.close()
    return render_template('index.html', manga_list=manga_list, filter_type=filter_type, filter_value=value, page=page, total_pages=total_pages)

if __name__ == '__main__':
    app.run(debug=True, port=5000)