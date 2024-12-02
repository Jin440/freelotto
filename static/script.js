document.addEventListener("DOMContentLoaded", () => {
    const drawSearchForm = document.getElementById("draw-search-form");
    const drawResultDiv = document.getElementById("draw-result");

    drawSearchForm.addEventListener("submit", async (e) => {
        e.preventDefault(); // 기본 폼 제출 동작 막기

        const drawNo = document.getElementById("draw-no").value;

        try {
            // 특정 회차 데이터를 가져오기
            const response = await fetch(`/lotto/${drawNo}`);
            const data = await response.json();

            if (data.success) {
                drawResultDiv.innerHTML = `
                    <h3>${data.draw_no}회 당첨 결과</h3>
                    <p>추첨일: ${data.draw_date}</p>
                    <p>당첨 번호: ${data.draw_numbers.join(', ')}</p>
                    <p>보너스 번호: ${data.bonus_number}</p>
                `;
            } else {
                drawResultDiv.innerHTML = `<p>오류: ${data.message}</p>`;
            }
        } catch (error) {
            console.error(error);
            drawResultDiv.innerHTML = ;
        }
    });
});

function deleteCoupon(couponId) {
    if (confirm(`쿠폰 ID ${couponId}을(를) 삭제하시겠습니까?`)) {
        fetch('/admin/coupons', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `action=delete&coupon_id=${couponId}` // key를 coupon_id로 전달
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            if (data.success) location.reload();
        });
    }
}

function fetchLottoDraws() {
    const youtubeHashtag = document.getElementById("hashtag_input").value.trim();

    if (!youtubeHashtag) {
        alert("유튜브 해시태그를 입력해주세요.");
        return;
    }

    fetch(`/lotto/draws/${encodeURIComponent(youtubeHashtag)}`)
        .then(response => response.json())
        .then(data => {
            const resultsDiv = document.getElementById("draw_results");
            resultsDiv.innerHTML = ""; // 기존 결과 초기화

            if (data.success) {
                const results = data.draws.map(
                    draw => `<p>${draw.date}: ${draw.numbers}</p>`
                );
                resultsDiv.innerHTML = results.join("");
            } else {
                resultsDiv.innerHTML = `<p>${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error("Error fetching draws:", error);
            alert("로또 추첨 기록을 불러오는 중 오류가 발생했습니다.");
        });
        
    fetch("/lotto/coupon/use", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        coupon_code: "LOTTO-123456",
        youtube_hashtag: "#example"
    })
});
}