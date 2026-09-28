import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import date, timedelta


# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="송탄고등학교 급식 영양 분석",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 송탄고등학교 급식 영양 분석")
st.write("송탄고등학교 중식 급식 데이터를 이용해 요일별 평균 단백질 함량을 분석합니다.")

# 송탄고등학교로 고정
SCHOOL_NAME = "송탄고등학교"

# 나이스 API 주소
SCHOOL_API_URL = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# =========================================================
# 2. 송탄고등학교 학교 정보 조회
# =========================================================

@st.cache_data
def get_school_info():
    """
    나이스 학교기본정보 API에서
    송탄고등학교의 교육청 코드와 학교 코드를 찾습니다.
    """

    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": SCHOOL_NAME
    }

    response = requests.get(
        SCHOOL_API_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    # 검색 결과가 없는 경우
    if "schoolInfo" not in data:
        return None

    rows = data["schoolInfo"][1].get("row", [])

    # 같은 이름의 학교가 있을 수 있으므로
    # 고등학교인 송탄고등학교만 선택
    for row in rows:
        if (
            row.get("SCHUL_NM") == SCHOOL_NAME
            and row.get("SCHUL_KND_SC_NM") == "고등학교"
        ):
            return {
                "ATPT_OFCDC_SC_CODE": row.get("ATPT_OFCDC_SC_CODE"),
                "SD_SCHUL_CODE": row.get("SD_SCHUL_CODE"),
                "ATPT_OFCDC_SC_NM": row.get("ATPT_OFCDC_SC_NM"),
                "ORG_RDNMA": row.get("ORG_RDNMA")
            }

    return None


# =========================================================
# 3. 날짜 범위 선택
# =========================================================

today = date.today()

# 기본값: 최근 30일
default_start = today - timedelta(days=30)
default_end = today

st.subheader("📅 분석 기간")

date_range = st.date_input(
    "분석할 날짜 범위를 선택하세요.",
    value=(default_start, default_end),
    max_value=today
)

if not isinstance(date_range, tuple) or len(date_range) != 2:
    st.info("시작일과 종료일을 모두 선택해 주세요.")
    st.stop()

start_date, end_date = date_range

if start_date > end_date:
    st.error("시작일은 종료일보다 빠르거나 같아야 합니다.")
    st.stop()


# =========================================================
# 4. 송탄고등학교 정보 가져오기
# =========================================================

try:
    school_info = get_school_info()

except requests.RequestException:
    st.error("나이스 학교정보 API에 연결할 수 없습니다.")
    st.stop()

except Exception:
    st.error("송탄고등학교의 학교 정보를 확인하는 중 오류가 발생했습니다.")
    st.stop()


if school_info is None:
    st.error("나이스에서 송탄고등학교의 학교 정보를 찾을 수 없습니다.")
    st.stop()


# 학교 정보 표시
st.info(
    f"🏫 {SCHOOL_NAME} · "
    f"{school_info['ATPT_OFCDC_SC_NM']} · "
    f"{school_info['ORG_RDNMA']}"
)


# =========================================================
# 5. 급식 데이터 가져오기
# =========================================================

@st.cache_data
def get_meal_data(
    atpt_code,
    school_code,
    start_ymd,
    end_ymd
):
    """
    선택한 기간의 송탄고등학교 중식 데이터를 가져옵니다.
    """

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": 2,  # 중식
        "MLSV_FROM_YMD": start_ymd,
        "MLSV_TO_YMD": end_ymd,
        "pSize": 1000,
        "pIndex": 1
    }

    response = requests.get(
        MEAL_API_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    # 조회 결과가 없는 경우
    if "mealServiceDietInfo" not in data:
        return pd.DataFrame()

    meal_info = data["mealServiceDietInfo"]

    if len(meal_info) < 2:
        return pd.DataFrame()

    rows = meal_info[1].get("row", [])

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


# =========================================================
# 6. API에서 급식 데이터 가져오기
# =========================================================

try:
    df = get_meal_data(
        school_info["ATPT_OFCDC_SC_CODE"],
        school_info["SD_SCHUL_CODE"],
        start_date.strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d")
    )

except requests.RequestException:
    st.error("나이스 급식식단정보 API에 연결할 수 없습니다.")
    st.stop()

except Exception:
    st.error("급식 데이터를 가져오는 중 오류가 발생했습니다.")
    st.stop()


# =========================================================
# 7. 급식 데이터가 없는 경우
# =========================================================

if df.empty:
    st.warning(
        "선택한 기간에는 송탄고등학교의 중식 급식 데이터가 없습니다."
    )
    st.stop()


# =========================================================
# 8. 날짜와 요일 처리
# =========================================================

df["급식일"] = pd.to_datetime(
    df["MLSV_YMD"],
    format="%Y%m%d",
    errors="coerce"
)

df = df.dropna(subset=["급식일"])

weekday_map = {
    0: "월요일",
    1: "화요일",
    2: "수요일",
    3: "목요일",
    4: "금요일",
    5: "토요일",
    6: "일요일"
}

df["요일"] = df["급식일"].dt.dayofweek.map(weekday_map)

# 월~금만 분석
weekday_order = [
    "월요일",
    "화요일",
    "수요일",
    "목요일",
    "금요일"
]

df_weekday = df[df["요일"].isin(weekday_order)].copy()


# =========================================================
# 9. 단백질 데이터 확인
# =========================================================

# 나이스 API의 실제 응답에서 단백질 관련 필드를 찾습니다.
# API가 사용하는 필드명이 변경되더라도 몇 가지 일반적인 이름을 확인합니다.

protein_candidates = [
    "PROTEIN",
    "PROTEIN_G",
    "PROT",
    "PROT_G",
    "단백질",
    "단백질(g)",
    "NTRT_PROT",
    "NTRT_PROTEIN"
]

protein_column = None

for column in protein_candidates:
    if column in df.columns:
        protein_column = column
        break


# =========================================================
# 10. 단백질 데이터가 없는 경우
# =========================================================

if protein_column is None:

    st.warning(
        "현재 나이스 급식식단정보에서 제공되는 데이터에는 "
        "단백질 함량이 없어 요일별 단백질 분석을 할 수 없습니다."
    )

    st.subheader("📋 선택한 기간의 송탄고등학교 중식")

    # 메뉴 표시용 데이터
    menu_df = df[["급식일", "DDISH_NM", "CAL_INFO"]].copy()

    menu_df["급식일"] = menu_df["급식일"].dt.strftime("%Y-%m-%d")

    menu_df = menu_df.rename(
        columns={
            "급식일": "급식일",
            "DDISH_NM": "중식 메뉴",
            "CAL_INFO": "칼로리"
        }
    )

    st.dataframe(
        menu_df,
        use_container_width=True,
        hide_index=True
    )

    st.stop()


# =========================================================
# 11. 단백질 값을 숫자로 변환
# =========================================================

df_weekday["단백질(g)"] = pd.to_numeric(
    df_weekday[protein_column],
    errors="coerce"
)

# 단백질 값이 실제로 있는 급식만 사용
protein_df = df_weekday.dropna(
    subset=["단백질(g)"]
).copy()


# =========================================================
# 12. 분석에 사용할 데이터가 부족한 경우
# =========================================================

total_meal_days = len(df_weekday)
protein_meal_days = len(protein_df)

if protein_meal_days == 0:

    st.warning(
        "선택한 기간의 급식 데이터에서 단백질 함량을 확인할 수 있는 날이 없습니다."
    )

    st.stop()


# =========================================================
# 13. 요일별 평균 단백질 계산
# =========================================================

weekday_average = (
    protein_df
    .groupby("요일", as_index=False)["단백질(g)"]
    .mean()
)

# 월요일~금요일 순서로 정렬
weekday_average["요일"] = pd.Categorical(
    weekday_average["요일"],
    categories=weekday_order,
    ordered=True
)

weekday_average = (
    weekday_average
    .sort_values("요일")
    .reset_index(drop=True)
)


# =========================================================
# 14. 분석 결과 숫자 표시
# =========================================================

highest_row = weekday_average.loc[
    weekday_average["단백질(g)"].idxmax()
]

highest_weekday = highest_row["요일"]
highest_protein = highest_row["단백질(g)"]


st.subheader("📊 분석 결과")

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "전체 급식 일수",
        f"{total_meal_days}일"
    )

with col2:
    st.metric(
        "단백질 확인 가능 급식 일수",
        f"{protein_meal_days}일"
    )


# =========================================================
# 15. 요일별 평균 단백질 막대그래프
# =========================================================

st.subheader("🥩 요일별 평균 단백질 함량")

fig = px.bar(
    weekday_average,
    x="요일",
    y="단백질(g)",
    text="단백질(g)",
    category_orders={
        "요일": weekday_order
    },
    labels={
        "요일": "요일",
        "단백질(g)": "평균 단백질 함량 (g)"
    },
    title="송탄고등학교 요일별 평균 단백질 함량"
)

# 막대 위에 숫자를 표시
fig.update_traces(
    texttemplate="%{text:.1f} g",
    textposition="outside",
    hovertemplate=(
        "<b>%{x}</b><br>"
        "평균 단백질: %{y:.1f} g"
        "<extra></extra>"
    )
)

fig.update_layout(
    yaxis_title="평균 단백질 함량 (g)",
    xaxis_title="요일",
    uniformtext_minsize=10,
    uniformtext_mode="hide"
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# =========================================================
# 16. 한 문장 분석 설명
# =========================================================

st.info(
    f"이 그래프로 알 수 있는 것: "
    f"송탄고등학교는 평균적으로 {highest_weekday}에 "
    f"단백질이 가장 많이 포함된 급식을 제공합니다."
)


# =========================================================
# 17. 선택한 기간의 중식 메뉴 확인
# =========================================================

st.subheader("🍱 선택한 기간의 송탄고등학교 중식 메뉴")

menu_df = df[[
    "급식일",
    "요일",
    "DDISH_NM",
    "CAL_INFO"
]].copy()

menu_df["급식일"] = menu_df["급식일"].dt.strftime("%Y-%m-%d")

menu_df = menu_df.rename(
    columns={
        "급식일": "급식일",
        "요일": "요일",
        "DDISH_NM": "중식 메뉴",
        "CAL_INFO": "칼로리"
    }
)

# 날짜가 빠른 순서로 표시
menu_df = menu_df.sort_values("급식일")


# =========================================================
# 18. 메뉴 이름의 <br/>을 줄바꿈으로 표시
# =========================================================

# st.dataframe에서는 HTML <br/> 대신 줄바꿈 문자로 변환
menu_df["중식 메뉴"] = (
    menu_df["중식 메뉴"]
    .astype(str)
    .str.replace("<br/>", "\n", regex=False)
    .str.replace("<br>", "\n", regex=False)
)


st.dataframe(
    menu_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "중식 메뉴": st.column_config.TextColumn(
            "중식 메뉴",
            width="large"
        ),
        "칼로리": st.column_config.TextColumn(
            "칼로리"
        )
    }
)
