from flask import Flask, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/books')
def get_books():
    conn = sqlite3.connect('Data/BookDekdb.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM books')
    books = cursor.fetchall()
    conn.close()
    return jsonify(books)

if __name__ == '__main__':
    app.run(debug=True)