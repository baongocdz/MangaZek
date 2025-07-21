import sqlite3

def check_db_connection():
    try:
        conn = sqlite3.connect('Data/BookDekdb.db')
        conn.close()
        return True
    except Exception as e:
        print(f"Database connection error: {e}")
        return False

def get_book_count():
    conn = sqlite3.connect('Data/BookDekdb.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM books')
    count = cursor.fetchone()[0]
    conn.close()
    return count