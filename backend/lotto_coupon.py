import sqlite3
from backend.config import DATABASE_PATH
import random
import string
from backend.config import get_db_connection


def get_db_connection():
    """
    SQLite 데이터베이스 연결 생성
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # 결과를 딕셔너리처럼 사용 가능
    return conn

def generate_coupon_code():
    import random, string
    prefix = "LOTTO-"
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def generate_coupon_code(length=10):
    """
    랜덤 쿠폰 코드 생성
    """
    prefix = "LOTTO"
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{random_part}"

def delete_coupon(coupon_id):
    """
    쿠폰을 삭제
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 쿠폰 ID로 삭제
        cursor.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))
        conn.commit()
        conn.close()

        return {"success": True, "message": f"쿠폰 ID {coupon_id}이(가) 삭제되었습니다."}
    except Exception as e:
        print("[ERROR] delete_coupon 함수 에러:", str(e))
        return {"success": False, "message": str(e)}

def create_coupon():
    """
    쿠폰 생성 및 저장
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        coupon_code = generate_coupon_code()
        cursor.execute("INSERT INTO coupons (coupon_code) VALUES (?)", (coupon_code,))
        conn.commit()
        conn.close()

        return {"success": True, "coupon_code": coupon_code}
    except Exception as e:
        return {"success": False, "message": str(e)}

def use_coupon(coupon_code, youtube_hashtag, selected_numbers):
    """
    쿠폰 사용 처리 함수
    coupon_code: 쿠폰 코드
    youtube_hashtag: 유튜브 해시태그
    selected_numbers: 사용자가 선택한 로또 번호
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 쿠폰 코드 확인
        cursor.execute("SELECT id FROM coupons WHERE coupon_code = ?", (coupon_code,))
        coupon = cursor.fetchone()
        if not coupon:
            return {"success": False, "message": "유효하지 않은 쿠폰 코드입니다."}

        coupon_id = coupon["id"]

        # 중복 사용 확인
        cursor.execute(
            "SELECT 1 FROM coupon_uses WHERE coupon_id = ? AND youtube_hashtag = ?",
            (coupon_id, youtube_hashtag),
        )
        if cursor.fetchone():
            return {"success": False, "message": "이 쿠폰은 해당 해시태그로 이미 사용되었습니다."}

        # 사용 기록 추가
        cursor.execute(
            "INSERT INTO coupon_uses (coupon_id, youtube_hashtag, selected_numbers) VALUES (?, ?, ?)",
            (coupon_id, youtube_hashtag, ','.join(map(str, selected_numbers))),
        )
        conn.commit()
        conn.close()

        return {"success": True, "message": f"쿠폰 {coupon_code}이(가) 성공적으로 사용되었습니다."}
    except Exception as e:
        print("[ERROR] use_coupon 함수 에러:", str(e))
        return {"success": False, "message": str(e)}

def get_all_coupons():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        coupons = cursor.execute("SELECT * FROM coupons").fetchall()
        conn.close()

        # Row 객체를 딕셔너리로 변환
        return [dict(row) for row in coupons]
    except Exception as e:
        print("[ERROR] get_all_coupons 함수 에러:", str(e))
        return []