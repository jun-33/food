import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 학교 급식 찾아보기")
st.write("학교를 검색하고 원하는 날짜의 중식 메뉴를 확인해 보세요.")


SCHOOL_API_URL = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# =========================================================
# 한국 시간 기준 오늘 날짜
# =========================================================

KST = ZoneInfo("Asia/Seoul")
today = datetime.now(KST).date()


# =========================================================
# 학교 이름 변환
# 예: 수도여고 → 수도여자고등학교
# =========================================================

def expand_school_name(name):
    name = name.strip()

    replacements = [
        ("여고", "여자고등학교"),
        ("남고", "남자고등학교"),
        ("여중", "여자중학교"),
        ("남중", "남자중학교"),
        ("고교", "고등학교"),
        ("고", "고등학교"),
        ("중교", "중학교"),
        ("중", "중학교"),
    ]

    for short, full in replacements:
        if name.endswith(short):
            return name[:-len(short)] + full

    return name


# =========================================================
# 학교 검색
# =========================================================

@st.cache_data(ttl=3600)
def search_schools(school_name):
    params = {
        "Type": "json",
        "SCHUL_NM": school_name
    }

    try:
        response = requests.get(
            SCHOOL_API_URL,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

    except Exception:
        return None, "API_ERROR"

    # 조회 결과가 없는 경우
    if "schoolInfo" not in data:
        return [], "NOT_FOUND"

    try:
        rows = data["schoolInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return [], "NOT_FOUND"

    return rows, "OK"


# =========================================================
# 급식 검색
# =========================================================

@st.cache_data(ttl=1800)
def get_meal(atpt_code, school_code, selected_date):
    date_string = selected_date.strftime("%Y%m%d")

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": date_string,
        "MLSV_TO_YMD": date_string,
        "pSize": "1000",
        "pIndex": "1"
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
        return None, "API_ERROR"

    if "mealServiceDietInfo" not in data:
        return None, "NOT_FOUND"

    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return None, "NOT_FOUND"

    if not rows:
        return None, "NOT_FOUND"

    return rows[0], "OK"


# =========================================================
# 학교 이름 입력
# =========================================================

school_name = st.text_input(
    "학교 이름",
    placeholder="예: 수도여고, 서울고, 한빛중학교"
)


# =========================================================
# 학교 검색 버튼
# =========================================================

if st.button("🔎 학교 찾기", type="primary"):

    if not school_name.strip():
        st.warning("학교 이름을 입력해 주세요.")
        st.stop()

    # 먼저 입력한 이름 그대로 검색
    schools, status = search_schools(school_name)

    # 검색 결과가 없으면 줄임말을 정식 이름으로 바꾸어 재검색
    if status == "NOT_FOUND":
        expanded_name = expand_school_name(school_name)

        if expanded_name != school_name:
            schools, status = search_schools(expanded_name)

    if status == "API_ERROR":
        st.error("학교 정보를 불러오는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.")

    elif status == "NOT_FOUND" or not schools:
        st.info("입력한 이름에 해당하는 학교를 찾지 못했습니다.")

    else:
        # 최대 5개가 반환되므로 선택할 수 있게 표시
        st.session_state["schools"] = schools


# =========================================================
# 학교 선택
# =========================================================

if "schools" in st.session_state:

    schools = st.session_state["schools"]

    st.subheader("🏫 학교 선택")

    school_options = []

    for school in schools:
        school_name_display = school.get("SCHUL_NM", "")
        region = school.get("LCTN_SC_NM", "")

        school_options.append(
            f"{school_name_display} ({region})"
        )

    selected_index = st.selectbox(
        "찾은 학교 중 하나를 선택하세요.",
        range(len(school_options)),
        format_func=lambda i: school_options[i]
    )

    selected_school = schools[selected_index]

    st.session_state["selected_school"] = selected_school


# =========================================================
# 날짜 선택
# =========================================================

if "selected_school" in st.session_state:

    selected_school = st.session_state["selected_school"]

    st.divider()

    st.subheader("📅 급식 날짜")

    selected_date = st.date_input(
        "날짜를 선택하세요.",
        value=today
    )

    st.caption(
        f"선택한 학교: {selected_school['SCHUL_NM']} "
        f"({selected_school['LCTN_SC_NM']})"
    )

    # =====================================================
    # 급식 조회
    # =====================================================

    meal, meal_status = get_meal(
        selected_school["ATPT_OFCDC_SC_CODE"],
        selected_school["SD_SCHUL_CODE"],
        selected_date
    )

    if meal_status == "API_ERROR":

        st.error(
            "급식 정보를 불러오는 중 문제가 발생했습니다. "
            "잠시 후 다시 시도해 주세요."
        )

    elif meal_status == "NOT_FOUND":

        st.info(
            f"{selected_date.strftime('%Y년 %m월 %d일')}에는 "
            "등록된 중식 급식 정보가 없습니다."
        )

    else:

        st.divider()

        st.subheader(
            f"🍚 {selected_date.strftime('%Y년 %m월 %d일')} 중식"
        )

        # -------------------------------------------------
        # 칼로리
        # -------------------------------------------------

        cal_info = meal.get("CAL_INFO", "")

        st.metric(
            "총 칼로리",
            cal_info if cal_info else "정보 없음"
        )

        # -------------------------------------------------
        # 메뉴
        # -------------------------------------------------

        st.markdown("### 🍽️ 메뉴")

        menu = meal.get("DDISH_NM", "")

        # <br/> 또는 <br>을 줄바꿈으로 변경
        menu = menu.replace("<br/>", "\n")
        menu = menu.replace("<br>", "\n")
        menu = menu.replace("<BR/>", "\n")
        menu = menu.replace("<BR>", "\n")

        # 메뉴를 한 줄씩 표시
        menu_items = [
            item.strip()
            for item in menu.split("\n")
            if item.strip()
        ]

        if menu_items:
            for item in menu_items:
                st.markdown(f"- {item}")
        else:
            st.info("등록된 메뉴 정보가 없습니다.")
