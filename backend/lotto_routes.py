from flask import Blueprint, render_template
from backend.lotto_api import fetch_latest_draw_no, fetch_draw_data
from backend.lotto_coupon import create_coupon, use_coupon, get_all_coupons, delete_coupon

lotto_routes = Blueprint("lotto_routes", __name__)

@lotto_routes.route("/lotto/latest")
def get_latest_lotto():
    latest_draw_no = fetch_latest_draw_no()
    if not latest_draw_no:
        return {"success": False, "message": "최신 회차를 찾을 수 없습니다."}
    return {"success": True, "data": fetch_draw_data(latest_draw_no)}

@lotto_routes.route("/lotto/<int:draw_no>")
def get_lotto_by_draw(draw_no):
    return {"success": True, "data": fetch_draw_data(draw_no)}

@lotto_routes.route("/admin/coupons", methods=["GET"])
def manage_coupons():
    try:
        coupons = get_all_coupons()
        return render_template("coupons.html", coupons=coupons)
    except Exception as e:
        print("[ERROR] manage_coupons 에러:", str(e))
        return render_template("error.html", error_message="쿠폰 데이터를 불러올 수 없습니다.")

@lotto_routes.route("/lotto/coupon", methods=["GET"])
def use_lotto_coupon():
    """
    로또 쿠폰 사용 페이지 렌더링
    """
    return render_template("lotto_coupon.html")