from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from backend.lotto_routes import lotto_routes
from backend.lotto_api import fetch_latest_draw_no, fetch_draw_data
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from backend.lotto_scraper import fetch_lotto_results
import sqlite3
import random
import string
import os
import logging
from google.cloud import storage

storage_client = storage.Client()
BUCKET_NAME = "freelotto"
GCS_DATABASE_PATH = "db/lotto.db"
LOCAL_DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'backend', 'db', 'lotto.db')

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

conn = sqlite3.connect(LOCAL_DATABASE_PATH)  # 메모리 대신 로컬 DB 사용
print(f"Database path: {LOCAL_DATABASE_PATH}")

app = Flask(__name__)
app.register_blueprint(lotto_routes)
app.secret_key = "781643719382"

def initialize_database():
    try:
        # GCS에서 데이터베이스 파일을 다운로드
        if not os.path.exists(LOCAL_DATABASE_PATH):  # 파일이 없다면 다운로드
            download_db_from_gcs()

        # 테이블 확인 후, 테이블이 없다면 새로 생성
        if not tables_exist():
            logging.warning("No tables found. Initializing tables...")
            initialize_tables()

        logging.info("Database initialized successfully.")

        # 테이블 상태 확인 (디버깅)
        check_tables()

        # GCS로 업로드 (업로드 필요시)
        upload_db_to_gcs()

    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise

# GCS에서 데이터베이스 파일을 다운로드하는 함수
def download_db_from_gcs():
    try:
        bucket = storage_client.get_bucket(BUCKET_NAME)
        blob = bucket.blob(GCS_DATABASE_PATH)
        logging.info(f"Downloading database to: {LOCAL_DATABASE_PATH}")  # 경로 출력
        blob.download_to_filename(LOCAL_DATABASE_PATH)  # 로컬 경로에 다운로드

        # 다운로드 후 파일 크기 확인
        file_size = os.path.getsize(LOCAL_DATABASE_PATH)
        logging.info(f"Downloaded file size: {file_size} bytes")

        if file_size == 0:
            logging.warning("The downloaded database is empty.")
        
        logging.info(f"Database downloaded from GCS to {LOCAL_DATABASE_PATH}")
    except Exception as e:
        logging.error(f"Error downloading database from GCS: {e}")
        raise

def upload_db_to_gcs():
    try:
        logging.info(f"Attempting to upload file from {LOCAL_DATABASE_PATH} to GCS.")

        if not os.path.exists(LOCAL_DATABASE_PATH):
            raise FileNotFoundError(f"The file at {LOCAL_DATABASE_PATH} was not found.")
        
        bucket = storage_client.get_bucket(BUCKET_NAME)
        blob = bucket.blob(GCS_DATABASE_PATH)
        
        logging.info(f"Uploading database from {LOCAL_DATABASE_PATH} to GCS at {GCS_DATABASE_PATH}")
        blob.upload_from_filename(LOCAL_DATABASE_PATH)  # 로컬에서 GCS로 업로드
        logging.info(f"Database uploaded to GCS from {LOCAL_DATABASE_PATH}")
    except Exception as e:
        logging.error(f"Error uploading database to GCS: {e}")
        raise

def check_tables():
    try:
        conn = sqlite3.connect(LOCAL_DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logging.info(f"Tables in the database: {tables}")

        # 테이블이 없으면, 경고 출력
        if not tables:
            logging.warning("No tables found in the database.")
        else:
            logging.info("Tables found in the database.")

    except sqlite3.Error as e:
        logging.error(f"Error checking tables: {e}")
    finally:
        conn.close()

def tables_exist():
    """테이블이 존재하는지 확인하는 함수"""
    conn = sqlite3.connect(LOCAL_DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    conn.close()
    logging.info(f"Tables found: {tables}")  # 테이블 목록 로그 출력
    return bool(tables)

def initialize_tables():
    """빈 데이터베이스에서 테이블을 생성하는 함수"""
    try:
        conn = sqlite3.connect(LOCAL_DATABASE_PATH)
        cursor = conn.cursor()

        # 테이블 생성 쿼리
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_code TEXT UNIQUE NOT NULL,
            is_used BOOLEAN NOT NULL DEFAULT 0
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS coupon_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_id INTEGER NOT NULL,
            youtube_hashtag TEXT NOT NULL,
            selected_numbers TEXT NOT NULL,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (coupon_id) REFERENCES coupons (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lotto_draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_no INTEGER NOT NULL,
            draw_date TEXT NOT NULL,
            youtube_hashtag TEXT NOT NULL
        );
        """)

        # 변경 사항 커밋
        conn.commit()
        logging.info("Database tables initialized successfully.")
        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Error initializing tables: {e}")
        raise

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            logging.warning(f"Unauthorized access attempt at {request.url} without login.")
            flash("로그인이 필요합니다.")
            return redirect(url_for("admin_login"))
        logging.info(f"User logged in, proceeding to {request.url}")
        return f(*args, **kwargs)
    return decorated_function

def query_database(query, params=(), fetch_one=False):
    try:
        logging.info(f"Executing query: {query} with params: {params}")
        conn = sqlite3.connect(LOCAL_DATABASE_PATH)  # 경로가 정확한지 확인
        conn.row_factory = sqlite3.Row  # 이 설정을 통해 반환되는 결과를 Row 객체로 설정
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        result = cursor.fetchone() if fetch_one else cursor.fetchall()

        # sqlite.Row 객체를 dict로 변환
        result = [dict(row) for row in result] if not fetch_one else dict(result)

        logging.info(f"Query executed successfully, result: {result}")
        return result
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return None

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

@app.before_first_request
def initialize_database():
    try:
        if not os.path.exists(LOCAL_DATABASE_PATH):  # 파일이 없다면 다운로드
            download_db_from_gcs()
        logging.info("Database initialized from GCS.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise

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

# 구글 클라우드 스토리지에서 파일 업로드 처리
@app.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        flash("파일이 없습니다.")
        logging.warning("No file part in the upload request.")
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':  # 파일 이름이 없는 경우
        flash("파일 이름이 없습니다.")
        logging.warning("No filename provided.")
        return redirect(request.url)

    # 데이터베이스 파일만 업로드할 수 있도록 제한 (예: 'lotto.db')
    if file.filename != 'lotto.db':
        flash("데이터베이스 파일만 업로드할 수 있습니다.")
        logging.warning(f"Invalid file uploaded: {file.filename}")
        return redirect(request.url)

    try:
        # GCS에 파일 업로드 (로컬에 임시로 저장한 후 업로드)
        file.save(LOCAL_DATABASE_PATH)  # 파일을 로컬에 저장
        upload_db_to_gcs()  # 업로드 함수 호출
        logging.info(f"Database file {file.filename} successfully uploaded.")
        flash(f"파일 {file.filename}이(가) 성공적으로 업로드되었습니다.")
        return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Error uploading file {file.filename}: {e}")
        flash(f"파일 업로드 중 오류 발생: {e}")
        return redirect(request.url)


# 구글 클라우드 스토리지에서 파일 다운로드 처리
@app.route("/download/database", methods=["GET"])
def download_database():
    try:
        # 데이터베이스 파일을 서버로부터 다운로드
        download_db_from_gcs()
        return send_file(LOCAL_DATABASE_PATH, as_attachment=True)  # 클라이언트에게 다운로드
    except Exception as e:
        logging.error(f"Error downloading database: {e}")
        flash("파일 다운로드 중 오류 발생")
        return redirect(url_for("index"))

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
    logging.error(f"Unhandled exception: {e}")
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
            # 동일 해시태그로 이미 사용된 쿠폰인지 확인
            existing_use = query_database(
                "SELECT 1 FROM coupon_uses WHERE coupon_id = ? AND youtube_hashtag = ?",
                (coupon_id, youtube_hashtag), fetch_one=True
            )
            if existing_use:
                return {
                    "success": False,
                    "message": f"이 쿠폰은 이미 유튜브 핸들 '{youtube_hashtag}'로 사용되었습니다."
                }

        # 쿠폰 사용 기록 추가
        query_database(
            """
            INSERT INTO coupon_uses (coupon_id, youtube_hashtag, selected_numbers)
            VALUES (?, ?, ?)
            """,
            (coupon_id, youtube_hashtag, ','.join(map(str, selected_numbers)))
        )

        # 쿠폰 사용 상태 업데이트
        query_database(
            "UPDATE coupons SET is_used = 1 WHERE id = ?",
            (coupon_id,)
        )

        # 쿠폰 사용 후 결과 반환
        return {
            "success": True,
            "message": "쿠폰이 성공적으로 사용되었습니다.",
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

    try:
        # 쿠폰 사용 기록 저장
        result = save_coupon_usage(coupon_code, youtube_hashtag, selected_numbers)

        if result["success"]:
            # 쿠폰 사용 후, Cloud Storage로 데이터베이스 업로드
            upload_db_to_gcs()
            return jsonify(result)  # 쿠폰 사용 결과 반환
        else:
            return jsonify(result)

    except Exception as e:
        logging.error(f"Error submitting coupon: {e}")
        return jsonify({"success": False, "message": "서버 오류가 발생했습니다."})

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
    try:
        coupons = query_database("SELECT * FROM coupons")

        if request.accept_mimetypes.best == 'application/json':
            # JSON으로 반환
            return jsonify({"success": True, "coupons": coupons})

        return render_template("admin_coupons.html", coupons=coupons)
    except Exception as e:
        logging.error(f"Error fetching coupons: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/admin/coupons/create", methods=["POST"])
@login_required
def create_coupon():
    try:
        coupon_code = generate_coupon_code()
        query_database(
            "INSERT INTO coupons (coupon_code, is_used) VALUES (?, ?)",
            (coupon_code, False)
        )
        logging.info(f"Coupon created: {coupon_code}")
        
        # 쿠폰 생성 후, Cloud Storage로 데이터베이스 업로드
        upload_db_to_gcs()
        
        return jsonify({"success": True, "coupon_code": coupon_code})
    except sqlite3.Error as e:
        logging.error(f"Error creating coupon: {e}")
        return jsonify({"success": False, "message": "쿠폰 생성 중 오류가 발생했습니다."}), 500
    
@app.route("/admin/coupons/delete", methods=["POST"])
def delete_coupon():
    try:
        data = request.json
        coupon_id = data.get("coupon_id")

        if not coupon_id:
            return jsonify({"success": False, "message": "쿠폰 ID가 필요합니다."}), 400

        query_database("DELETE FROM coupons WHERE id = ?", (coupon_id,))
        logging.info(f"Coupon deleted: {coupon_id}")
        
        # 쿠폰 삭제 후, Cloud Storage로 데이터베이스 업로드
        upload_db_to_gcs()
        
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

@app.before_request
def log_request_info():
    logging.info(f"Request URL: {request.url}")
    logging.info(f"Request method: {request.method}")
    logging.info(f"Request data: {request.data}")

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
    check_tables()
    app.run(host="0.0.0.0", port=5000)  # Flask 애플리케이션 실행
