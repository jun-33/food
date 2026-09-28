import streamlit as st
import requests
import re
from datetime import datetime
from zoneinfo import ZoneInfo


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="우리 학교 달력별 급식",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 우리 학교 달력별 급식")
st.caption("송탄고등학교의 날짜별 중식 급식을 확인해 보세요.")


# =========================================================
# 송탄고등학교 정보
# =========================================================

ATPT_OFCDC_SC_CODE = "J10"
SD_SCHUL_CODE = "7530480"

MEAL_API_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# =========================================================
# 한국 시간
# =========================================================

KST = ZoneInfo("Asia/Seoul")
today = datetime.now(KST).date()


# =========================================================
# 급식 정보 가져오기
# =========================================================

@st.cache_data(ttl=1800)
def get_meal(selected_date):

    date_string = selected_date.strftime("%Y%m%d")

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": ATPT_OFCDC_SC_CODE,
        "SD_SCHUL_CODE": SD_SCHUL_CODE,
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": date_string,
        "MLSV_TO_YMD": date_string
    }

    try:
        response = requests.get(
            MEAL_API_URL,
            params=params,
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

    except Exception:
        return None

    if "mealServiceDietInfo" not in data:
        return None

    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return None

    if not rows:
        return None

    return rows[0]


# =========================================================
# 메뉴에서 알레르기 번호 처리
# =========================================================

def remove_allergy_numbers(menu):
    """
    메뉴 뒤의 괄호 속 알레르기 번호를 제거한다.

    예:
    쌀밥(5) → 쌀밥
    김치찌개(5.6.9) → 김치찌개
    """

    return re.sub(r"\s*\([^)]*\)", "", menu)


# =========================================================
# 날짜 + 스위치
# =========================================================

col1, col2 = st.columns([2, 1])

with col1:
    selected_date = st.date_input(
        "📅 날짜 선택",
        value=today
    )

with col2:
    st.write("")
    st.write("")

    show_allergy = st.toggle(
        "알레르기 정보 보기",
        value=True
    )


# =========================================================
# 선택한 날짜 표시
# =========================================================

st.divider()

st.subheader(
    f"📅 {selected_date.strftime('%Y년 %m월 %d일')} 중식"
)


# =========================================================
# 급식 조회
# =========================================================

meal = get_meal(selected_date)


# 급식이 없는 경우
if meal is None:

    st.info("🍽️ 급식이 없는 날입니다.")

    st.stop()


# =========================================================
# 급식 데이터
# =========================================================

menu_text = meal.get("DDISH_NM", "")
cal_info = meal.get("CAL_INFO", "")

# <br/>, <br> 등을 줄바꿈으로 변경
menu_text = re.sub(
    r"<br\s*/?>",
    "\n",
    menu_text,
    flags=re.IGNORECASE
)

# 메뉴를 각각 분리
menu_items = [
    item.strip()
    for item in menu_text.split("\n")
    if item.strip()
]


# =========================================================
# 알레르기 번호 표시 여부
# =========================================================

if not show_allergy:
    display_items = [
        remove_allergy_numbers(item)
        for item in menu_items
    ]
else:
    display_items = menu_items


# =========================================================
# 메뉴 개수 / 칼로리
# =========================================================

calorie_display = cal_info if cal_info else "정보 없음"

stat1, stat2 = st.columns(2)

with stat1:
    st.metric(
        "🍴 메뉴 가짓수",
        f"{len(display_items)}가지"
    )

with stat2:
    st.metric(
        "🔥 칼로리",
        calorie_display
    )


st.divider()


# =========================================================
# 메뉴 카드
# =========================================================

st.subheader("🍽️ 오늘의 메뉴")


if display_items:

    # 한 줄에 3개의 메뉴 카드
    columns = st.columns(3)

    for index, menu in enumerate(display_items):

        with columns[index % 3]:

            st.markdown(
                f"""
                <div style="
                    border: 1px solid #e5e7eb;
                    border-radius: 14px;
                    padding: 20px;
                    margin-bottom: 16px;
                    background-color: #ffffff;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
                    min-height: 80px;
                    display: flex;
                    align-items: center;
                ">
                    <div style="
                        font-size: 18px;
                        font-weight: 600;
                        line-height: 1.5;
                    ">
                        {menu}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

else:

    st.info("등록된 메뉴가 없습니다.")
