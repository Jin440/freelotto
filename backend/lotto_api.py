import requests
import datetime

API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="

def fetch_latest_draw_no():
    """
    최신 회차 번호를 확인.
    """
    # 현재 날짜 기반으로 최신 회차 추정
    today = datetime.date.today()
    start_date = datetime.date(2002, 12, 7)  # 로또 첫 회차가 시작된 날짜
    delta = today - start_date
    estimated_latest_draw_no = delta.days // 7 + 1  # 대략적인 최신 회차 계산 (7일 단위로)

    while estimated_latest_draw_no > 0:
        # API를 통해 해당 회차가 존재하는지 확인
        response = requests.get(API_URL + str(estimated_latest_draw_no))
        data = response.json()
        
        # 회차가 존재하면 그 회차를 반환
        if data["returnValue"] == "success":
            return estimated_latest_draw_no
        
        # 존재하지 않으면 이전 회차를 시도
        estimated_latest_draw_no -= 1
    
    # 회차를 찾을 수 없으면 None 반환
    return None

def fetch_draw_data(draw_no):
    """
    특정 회차 번호의 데이터를 가져옵니다.
    """
    API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="
    try:
        response = requests.get(API_URL + str(draw_no))
        response.raise_for_status()
        data = response.json()

        if data["returnValue"] != "success":
            return {"success": False, "message": f"{draw_no} 회차 데이터를 찾을 수 없습니다."}

        # API에서 필요한 데이터 추출
        return {
            "success": True,
            "draw_no": data["drwNo"],
            "draw_date": data["drwNoDate"],
            "draw_numbers": [data[f"drwtNo{i}"] for i in range(1, 7)],
            "bonus_number": data["bnusNo"],
            "prize_1st": int(data["firstWinamnt"]),
            "prize_1st_winners": int(data["firstPrzwnerCo"]),  # 1등 당첨자 수
        }
    except Exception as e:
        logging.error(f"Error fetching draw data: {e}")
        return {"success": False, "message": "API 요청 실패"}