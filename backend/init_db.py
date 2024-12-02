import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'db', 'lotto.db')

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 쿠폰 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coupon_code TEXT UNIQUE NOT NULL,
        is_used BOOLEAN NOT NULL DEFAULT 0
    )
    """)
    
    # 쿠폰 사용 기록 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupon_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coupon_id INTEGER NOT NULL,
        youtube_hashtag TEXT NOT NULL,
        selected_numbers TEXT NOT NULL,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (coupon_id) REFERENCES coupons (id)
    )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized.")

if __name__ == "__main__":
    init_db()