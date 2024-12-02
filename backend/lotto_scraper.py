import requests
from bs4 import BeautifulSoup

def fetch_lotto_results():
    url = "https://dhlottery.co.kr/gameResult.do?method=byWin"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", class_="tbl_data tbl_data_col")

        if not table:
            raise ValueError("로또 결과 테이블을 찾을 수 없습니다.")

        rows = table.find_all("tr")[2:]  # 헤더를 제외한 데이터
        results = []
        for row in rows[:3]:  # 1등, 2등, 3등만 가져오기
            cols = row.find_all("td")

            # 전처리: 쉼표 및 "원" 제거 후 숫자로 변환
            prize_amount = int(cols[1].text.strip().replace(',', '').replace('원', ''))
            winner_count = int(cols[2].text.strip().replace(',', ''))

            results.append({
                "rank": cols[0].text.strip(),
                "prize_amount": prize_amount,  # 총 당첨금
                "winner_count": winner_count,  # 당첨자 수
            })

            # 디버깅: 변환된 데이터 출력
            print(f"Rank: {cols[0].text.strip()}, Prize Amount: {prize_amount}, Winner Count: {winner_count}")

        return {"success": True, "results": results}
    except Exception as e:
        print("크롤링 실패:", str(e))
        return {"success": False, "message": str(e)}