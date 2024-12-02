import sqlite3
import os

# 데이터베이스 파일 경로 설정
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "db", "lotto.db")

def get_db_connection():
    """
    SQLite 데이터베이스 연결 생성
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # 결과를 딕셔너리처럼 사용 가능
    return conn