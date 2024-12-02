from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from backend.lotto_routes import lotto_routes
from backend.lotto_api import fetch_latest_draw_no, fetch_draw_data
from backend.lotto_coupon import create_coupon, use_coupon, get_all_coupons, delete_coupon
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from backend.lotto_scraper import fetch_lotto_results
import sqlite3
import random
import string
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'db', 'lotto.db')

app = Flask(__name__)
app.register_blueprint(lotto_routes)
app.secret_key = "781643719382"

def initialize_database():
    """
    데이터베이스 파일이 존재하지 않을 경우 생성하고 테이블을 초기화합니다.
    """
    try:
        if not os.path.exists(DATABASE_PATH):
            os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
            logging.info(f"Database directory created at: {os.path.dirname(DATABASE_PATH)}")

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        logging.info(f"Connected to database at: {DATABASE_PATH}")

        create_table_query = """
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_code TEXT UNIQUE NOT NULL,
            is_used BOOLEAN NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS coupon_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_id INTEGER NOT NULL,
            youtube_hashtag TEXT NOT NULL,
            selected_numbers TEXT NOT NULL,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (coupon_id) REFERENCES coupons (id)
        );

        CREATE TABLE IF NOT EXISTS lotto_draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_no INTEGER NOT NULL,
            draw_date TEXT NOT NULL,
            youtube_hashtag TEXT NOT NULL
        );
        """
        logging.info("Executing table creation queries...")
        cursor.executescript(create_table_query)
        conn.commit()
        logging.info("Database tables created successfully.")

    except sqlite3.Error as e:
        logging.error(f"Error initializing database: {e}")
        raise

    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        app.logger.info(f"Session status in login_required: {session.get('logged_in')}")  # 세션 상태 확인
        if not session.get("logged_in"):  # 로그인 여부 확인
            app.logger.info("Unauthorized access detected. Redirecting to login.")
            flash("로그인이 필요합니다.")
            return redirect(url_for("admin_login"))
        app.logger.info("Authorized access granted.")
        return f(*args, **kwargs)
    return decorated_function

def query_database(query, params=(), fetch_one=False):
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    result = cursor.fetchone() if fetch_one else cursor.fetchall()
    conn.close()
    return result

def generate_coupon_code():
    """
    랜덤한 12자리 쿠폰 코드 생성
    """
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def calculate_draw_date(draw_no):
    """
    1회차 추첨일(2002-12-07)을 기준으로 주어진 회차의 추첨일 계산
    """
    base_date = datetime(2002, 12, 7)  # 1회차 추첨일
    days_since_first_draw = (draw_no - 1) * 7  # 매주 토요일 추첨
    return base_date + timedelta(days=days_since_first_draw)

# 최신 회차 캐싱
@lru_cache(maxsize=1)
def get_cached_latest_draw():
    latest_draw_no = fetch_latest_draw_no()
    return fetch_draw_data(latest_draw_no) if latest_draw_no else None

@app.template_filter("format_price")
def format_price(value):
    """
    숫자를 천 단위로 쉼표를 넣어서 반환합니다.
    """
    try:
        return f"{value:,}"
    except ValueError:
        return value

@app.route("/")
def index():
    """
    메인 페이지
    """
    # 공식 API에서 최신 데이터 가져오기
    latest_draw_no = 1148  # 최신 회차 번호 (예시)
    latest_data = fetch_draw_data(latest_draw_no)

    if not latest_data["success"]:
        logging.error(f"공식 API 데이터 가져오기 실패: {latest_data['message']}")
        latest_data = {}

    # 동행복권 웹사이트에서 데이터 크롤링
    lotto_results = fetch_lotto_results()

    if not lotto_results["success"]:
        logging.error(f"로또 크롤링 실패: {lotto_results['message']}")
        lotto_results = {"results": []}

    # 1등 데이터 추가
    if latest_data:
        first_prize = {
            "rank": "1등",
            "prize_amount": latest_data["prize_1st"],  # 1등 당첨금 그대로 사용
            "winner_count": latest_data["prize_1st_winners"],  # 1등 당첨자 수
        }
        lotto_results["results"] = [first_prize] + lotto_results["results"][:2]  # 1등 + 2등, 3등만 표시

    return render_template(
        "index.html", latest_data=latest_data, lotto_results=lotto_results["results"]
    )

def home():
    return "Hello, Cloudtype!"

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "dltpwls" and password == "781643719382":
            session["logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("잘못된 아이디 또는 비밀번호입니다.")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html")

@app.route("/admin")
@login_required
def admin_dashboard():
    return render_template("admin.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()  # 세션 데이터 완전히 초기화
    response = redirect(url_for("admin_login"))
    response.delete_cookie("session")  # 세션 쿠키 삭제
    app.logger.info("Session cleared and cookie deleted on logout.")
    flash("성공적으로 로그아웃되었습니다.")
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    # 예상치 못한 예외에 대해서만 처리
    app.logger.error(f"Unhandled exception: {e}")
    return {"success": False, "message": "서버 오류가 발생했습니다."}, 500

@app.route("/lotto/coupon", methods=["GET"])
def coupon_page():
    """
    쿠폰 조회 페이지 렌더링
    """
    return render_template("lotto_coupon.html")

@app.route("/lotto/check/<int:draw_no>", methods=["GET"])
def get_draw_data_by_number(draw_no):
    try:
        draw_data = fetch_draw_data(draw_no)
        if draw_data["success"]:
            return jsonify({"success": True, "data": draw_data})
        return jsonify({"success": False, "message": f"{draw_no} 회차 데이터를 찾을 수 없습니다."})
    except Exception as e:
        logging.error(f"Error fetching draw data for draw_no {draw_no}: {e}")
        return jsonify({"success": False, "message": "서버 오류가 발생했습니다."})


# 최신 회차와 사용자가 선택한 번호 비교
@app.route("/lotto/check", methods=["GET"])
def check_lotto_result():
    latest_draw_no = fetch_latest_draw_no()
    if not latest_draw_no:
        return jsonify({"success": False, "message": "최신 회차를 찾을 수 없습니다."})

    latest_data = fetch_draw_data(latest_draw_no)
    if not latest_data:
        return jsonify({"success": False, "message": "최신 회차 데이터를 불러올 수 없습니다."})

    selected_numbers = [6, 11, 17, 19, 40, 43]  # 하드코딩된 값
    matched_numbers = [num for num in selected_numbers if num in latest_data['draw_numbers']]

    return jsonify({
        "success": True,
        "latest_draw_no": latest_draw_no,
        "matched_numbers": matched_numbers
    })

# 쿠폰 사용 기록 저장
def save_coupon_usage(coupon_code, youtube_hashtag, selected_numbers):
    try:
        # 쿠폰 존재 여부 및 사용 여부 확인
        coupon = query_database(
            "SELECT id, is_used FROM coupons WHERE coupon_code = ?",
            (coupon_code,), fetch_one=True
        )
        if not coupon:
            return {"success": False, "message": "유효하지 않은 쿠폰 코드입니다."}

        coupon_id = coupon["id"]
        is_used = coupon["is_used"]

        # 이미 사용된 쿠폰인지 확인
        if is_used:
            # 특정 해시태그로 동일 쿠폰을 이미 사용했는지 확인
            existing_use = query_database(
                "SELECT 1 FROM coupon_uses WHERE coupon_id = ? AND youtube_hashtag = ?",
                (coupon_id, youtube_hashtag), fetch_one=True
            )
            if existing_use:
                return {
                    "success": False,
                    "message": f"이 쿠폰은 이미 유튜브 핸들 '{youtube_hashtag}'로 사용되었습니다."
                }

            # 현재 해시태그가 사용한 쿠폰 수 확인
            usage_count = query_database(
                """
                SELECT COUNT(*) AS usage_count
                FROM coupon_uses
                WHERE youtube_hashtag = ?
                """,
                (youtube_hashtag,), fetch_one=True
            )["usage_count"]

            # 해시태그가 5개 미만의 쿠폰을 사용했다면 중복 사용 불가
            if usage_count < 5:
                return {
                    "success": False,
                    "message": f"이 핸들 '{youtube_hashtag}'는 5개 이상의 쿠폰을 사용하지 않았습니다. 아직 사용하지 않은 쿠폰을 찾아보세요!"
                }

        # 회차 계산: fetch_latest_draw_no + 1
        latest_draw_no = fetch_latest_draw_no()
        next_draw_no = latest_draw_no + 1 if latest_draw_no else 1

        # 추첨일 계산
        base_date = datetime(2002, 12, 7)
        draw_date = base_date + timedelta(weeks=next_draw_no - 1)

        # 쿠폰 사용 기록 추가
        query_database(
            """
            INSERT INTO coupon_uses (coupon_id, youtube_hashtag, selected_numbers)
            VALUES (?, ?, ?)
            """,
            (coupon_id, youtube_hashtag, ','.join(map(str, selected_numbers)))
        )

        # 쿠폰을 사용된 상태로 업데이트
        query_database(
            "UPDATE coupons SET is_used = 1 WHERE id = ?",
            (coupon_id,)
        )

        # 회차와 추첨일을 lotto_draws에 저장
        query_database(
            """
            INSERT INTO lotto_draws (draw_no, draw_date, youtube_hashtag)
            VALUES (?, ?, ?)
            """,
            (next_draw_no, draw_date.strftime('%Y-%m-%d'), youtube_hashtag)
        )

        return {
            "success": True,
            "message": f"쿠폰 사용 완료. 다음 추첨 회차: {next_draw_no}, 추첨일: {draw_date.strftime('%Y-%m-%d')}",
            "selected_numbers": selected_numbers
        }

    except Exception as e:
        logging.error(f"Error saving coupon usage: {e}")
        return {"success": False, "message": "서버 오류가 발생했습니다."}
    
# 번호 비교 함수 (사용자가 선택한 번호와 최신 당첨 번호 비교)
def compare_numbers(latest_numbers, selected_numbers):
    """
    최신 당첨 번호와 사용자가 선택한 번호를 비교하여 일치하는 번호를 반환
    """
    return [num for num in selected_numbers if num in latest_numbers]

# 데이터베이스에서 사용자가 선택한 번호를 조회
def get_user_selected_numbers():
    """
    예시로 하드코딩된 값 반환 (실제 구현 시 데이터베이스 조회 필요)
    """
    return [6, 11, 17, 19, 40, 43]

# 데이터베이스에서 총 사용한 쿠폰의 수를 조회
def get_total_draw_count():
    """
    데이터베이스에서 총 사용된 쿠폰의 수를 조회
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM coupon_uses")
    total_draws = cursor.fetchone()[0]
    conn.close()
    return total_draws

# 데이터베이스 연결
def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"[ERROR] Database connection failed: {e}")
        raise

# 쿠폰 제출을 처리하는 라우트
@app.route("/lotto/coupon/submit", methods=["POST"])
def submit_coupon():
    data = request.json
    coupon_code = data.get("coupon_code")
    youtube_hashtag = data.get("youtube_hashtag")
    selected_numbers = data.get("selected_numbers")

    if not coupon_code or not youtube_hashtag or not selected_numbers:
        return jsonify({"success": False, "message": "모든 필드를 입력해주세요."})

    return jsonify(save_coupon_usage(coupon_code, youtube_hashtag, selected_numbers))

@app.route("/gamerule", methods=["GET"])
def game_rule():
    """
    게임 방법 페이지 렌더링
    """
    return render_template("gamerule.html")

@app.route("/lotto/coupon/uses", methods=["GET"])
@login_required
def get_coupon_uses():
    """
    쿠폰 사용 내역 페이지
    """
    try:
        # 쿠폰 사용 내역 가져오기 (중복 제거된 쿼리 사용)
        coupon_uses = query_database("""
            SELECT 
                cu.id, 
                cu.coupon_id, 
                cu.selected_numbers, 
                cu.youtube_hashtag, 
                cu.used_at, 
                c.coupon_code, 
                ld.draw_no
            FROM 
                coupon_uses cu
            JOIN 
                coupons c ON cu.coupon_id = c.id
            LEFT JOIN 
                (SELECT youtube_hashtag, MAX(draw_no) AS draw_no
                 FROM lotto_draws
                 GROUP BY youtube_hashtag) ld
            ON 
                cu.youtube_hashtag = ld.youtube_hashtag;
        """)

        # 쿠폰 데이터를 리스트로 변환
        coupon_uses_list = [
            dict(row, selected_numbers=row["selected_numbers"].split(','))
            for row in coupon_uses
        ]

        return render_template(
            "admin_use_coupons.html",
            coupon_uses=coupon_uses_list
        )

    except Exception as e:
        logging.error(f"Error fetching coupon uses: {e}")
        return jsonify({"success": False, "message": "서버 오류가 발생했습니다."})

@app.route("/admin/coupons", methods=["GET"])
@login_required
def get_coupons_page():
    """
    쿠폰 조회 페이지 또는 API
    """
    try:
        coupons = query_database("SELECT * FROM coupons")
        
        # 요청 헤더에서 JSON 요청 여부 확인
        accept_header = request.headers.get("Accept", "")
        if "application/json" in accept_header:
            return jsonify({"success": True, "coupons": [dict(row) for row in coupons]})

        # HTML 페이지 반환
        return render_template("admin_coupons.html", coupons=coupons)

    except Exception as e:
        logging.error(f"Error fetching coupons: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/admin/coupons/create", methods=["POST"])
@login_required
def create_coupon():
    """
    쿠폰 생성 API
    """
    try:
        coupon_code = generate_coupon_code()
        query_database(
            "INSERT INTO coupons (coupon_code, is_used) VALUES (?, ?)",
            (coupon_code, False)
        )
        logging.info(f"Coupon created: {coupon_code}")
        return jsonify({"success": True, "coupon_code": coupon_code})
    except sqlite3.Error as e:
        logging.error(f"Error creating coupon: {e}")
        return jsonify({"success": False, "message": "쿠폰 생성 중 오류가 발생했습니다."}), 500
    
@app.route("/admin/coupons/delete", methods=["POST"])
def delete_coupon():
    """
    쿠폰 삭제 API
    """
    try:
        data = request.json
        coupon_id = data.get("coupon_id")

        if not coupon_id:
            return jsonify({"success": False, "message": "쿠폰 ID가 필요합니다."}), 400

        query_database("DELETE FROM coupons WHERE id = ?", (coupon_id,))
        logging.info(f"Coupon deleted: {coupon_id}")
        return jsonify({"success": True, "message": f"Coupon ID {coupon_id} deleted."})
    except sqlite3.Error as e:
        logging.error(f"Error deleting coupon: {e}")
        return jsonify({"success": False, "message": "쿠폰 삭제 중 오류가 발생했습니다."}), 500

@app.route("/api/coupons", methods=["GET"])
def get_coupons_api():
    """
    쿠폰 목록을 API 형태로 반환하는 라우트
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM coupons")
        coupons = cursor.fetchall()
        conn.close()

        # 응답 데이터 포맷
        coupons_list = [{"id": coupon[0], "coupon_code": coupon[1]} for coupon in coupons]

        return jsonify({"success": True, "coupons": coupons_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/lotto/coupon/lookup", methods=["GET"])
def lookup_coupon():
    hashtag = request.args.get("hashtag")
    if not hashtag:
        return jsonify({"success": False, "message": "유튜브 핸들을 입력해주세요."})

    try:
        # 데이터 조회
        coupons = query_database("""
            SELECT 
                c.coupon_code,
                cu.selected_numbers,
                cu.used_at,
                ld.draw_no,
                ld.draw_date
            FROM 
                coupon_uses cu
            JOIN 
                coupons c ON cu.coupon_id = c.id
            LEFT JOIN 
                (SELECT DISTINCT youtube_hashtag, draw_no, draw_date 
                FROM lotto_draws) ld ON cu.youtube_hashtag = ld.youtube_hashtag
            WHERE 
                cu.youtube_hashtag = ?
        """, (hashtag,))

        # 해당 해시태그로 사용된 쿠폰 수 계산
        used_coupons_count = query_database("""
            SELECT COUNT(*) AS count
            FROM coupon_uses
            WHERE youtube_hashtag = ?
        """, (hashtag,), fetch_one=True)["count"]

        # 결과 처리
        coupon_list = [
            {
                "coupon_code": row["coupon_code"],
                "selected_numbers": row["selected_numbers"].split(','),
                "used_at": row["used_at"],
                "draw_no": row["draw_no"],
                "draw_date": row["draw_date"],
            }
            for row in coupons
        ]

        return jsonify({"success": True, "data": coupon_list, "used_coupons_count": used_coupons_count})

    except Exception as e:
        logging.error(f"Error looking up coupons: {e}")
        return jsonify({"success": False, "message": "서버 오류가 발생했습니다."})

    
@app.route("/debug/latest_draw", methods=["GET"])
def debug_latest_draw():
    try:
        data = get_cached_latest_draw()
        return jsonify({"latest_draw_no": fetch_latest_draw_no(), "draw_data": data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == "__main__":
    initialize_database()  # 데이터베이스 초기화
    app.run(host="0.0.0.0", port=5000)  # Flask 애플리케이션 실행