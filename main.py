import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
from datetime import date, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="송탄고등학교 급식 영양 분석",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 송탄고등학교 급식 영양 분석")

st.write(
    "송탄고등학교의 중식 급식 데이터를 이용해 "
    "요일별 평균 단백질 함량을 분석합니다."
)


# =========================================================
# 2. 송탄고등학교 정보
# =========================================================

# 학교는 송탄고등학교로 고정
SCHOOL_NAME = "송탄고등학교"

# 나이스 API 주소
SCHOOL_API_URL = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# =========================================================
# 3. 송탄고등학교 학교 코드 조회
# =========================================================

@st.cache_data
def get_school_info():
    """
    나이스 학교기본정보 API에서
    송탄고등학교의 교육청 코드와 학교 코드를 가져옵니다.
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

    if len(data["schoolInfo"]) < 2:
        return None

    rows = data["schoolInfo"][1].get("row", [])

    # 송탄고등학교인 경우만 선택
    for row in rows:

        if (
            row.get("SCHUL_NM") == SCHOOL_NAME
            and row.get("SCHUL_KND_SC_NM") == "고등학교"
        ):
            return {
                "ATPT_OFCDC_SC_CODE": row.get(
                    "ATPT_OFCDC_SC_CODE"
                ),
                "SD_SCHUL_CODE": row.get(
                    "SD_SCHUL_CODE"
                ),
                "ATPT_OFCDC_SC_NM": row.get(
                    "ATPT_OFCDC_SC_NM"
                ),
                "ORG_RDNMA": row.get(
                    "ORG_RDNMA"
                )
            }

    return None


# =========================================================
# 4. 학교 정보 가져오기
# =========================================================

try:

    school_info = get_school_info()

except requests.RequestException:

    st.error(
        "나이스 학교정보 API에 연결할 수 없습니다."
    )

    st.stop()

except Exception:

    st.error(
        "송탄고등학교의 학교 정보를 확인하는 중 "
        "오류가 발생했습니다."
    )

    st.stop()


if school_info is None:

    st.error(
        "나이스에서 송탄고등학교의 학교 정보를 "
        "찾을 수 없습니다."
    )

    st.stop()


# 학교 정보 표시
st.info(
    f"🏫 {SCHOOL_NAME} · "
    f"{school_info['ATPT_OFCDC_SC_NM']} · "
    f"{school_info['ORG_RDNMA']}"
)


# =========================================================
# 5. 날짜 범위 선택
# =========================================================

st.subheader("📅 분석 기간")

# 한국 시간 기준 오늘
today = datetime_now = date.today()

# 오늘 급식은 아직 집계되지 않을 수 있으므로
# 가장 최근 선택 가능 날짜를 어제로 설정
yesterday = today - timedelta(days=1)

# 기본값: 최근 30일
default_start = yesterday - timedelta(days=29)
default_end = yesterday

date_range = st.date_input(
    "분석할 날짜 범위를 선택하세요.",
    value=(default_start, default_end),
    max_value=yesterday
)


# 날짜를 제대로 두 개 선택했는지 확인
if not isinstance(date_range, tuple) or len(date_range) != 2:

    st.info(
        "시작일과 종료일을 모두 선택해 주세요."
    )

    st.stop()


start_date, end_date = date_range


# 날짜 순서 확인
if start_date > end_date:

    st.error(
        "시작일은 종료일보다 빠르거나 같아야 합니다."
    )

    st.stop()


# =========================================================
# 6. 급식 데이터 가져오기
# =========================================================

@st.cache_data
def get_meal_data(
    atpt_code,
    school_code,
    start_ymd,
    end_ymd
):
    """
    선택한 기간의 송탄고등학교 중식 데이터를
    나이스 급식식단정보 API에서 가져옵니다.
    """

    params = {
        "Type": "json",

        # 교육청 코드
        "ATPT_OFCDC_SC_CODE": atpt_code,

        # 송탄고등학교 코드
        "SD_SCHUL_CODE": school_code,

        # 2 = 중식
        "MMEAL_SC_CODE": 2,

        # 조회 시작일
        "MLSV_FROM_YMD": start_ymd,

        # 조회 종료일
        "MLSV_TO_YMD": end_ymd,

        # 한 번에 충분한 수의 데이터 요청
        "pSize": 1000,

        # 첫 번째 페이지
        "pIndex": 1
    }

    response = requests.get(
        MEAL_API_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    # API에 급식 데이터가 없는 경우
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
# 7. API에서 급식 데이터 불러오기
# =========================================================

try:

    df = get_meal_data(
        school_info["ATPT_OFCDC_SC_CODE"],
        school_info["SD_SCHUL_CODE"],
        start_date.strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d")
    )

except requests.RequestException:

    st.error(
        "나이스 급식식단정보 API에 연결할 수 없습니다."
    )

    st.stop()

except Exception:

    st.error(
        "급식 데이터를 가져오는 중 오류가 발생했습니다."
    )

    st.stop()


# =========================================================
# 8. 급식 데이터가 없는 경우
# =========================================================

if df.empty:

    st.warning(
        "선택한 기간에는 송탄고등학교의 "
        "중식 급식 데이터가 없습니다."
    )

    st.stop()


# =========================================================
# 9. 날짜와 요일 처리
# =========================================================

df["급식일"] = pd.to_datetime(
    df["MLSV_YMD"],
    format="%Y%m%d",
    errors="coerce"
)

# 날짜를 읽지 못한 데이터 제거
df = df.dropna(
    subset=["급식일"]
).copy()


# 요일 번호를 한국어 요일로 변환
weekday_map = {
    0: "월요일",
    1: "화요일",
    2: "수요일",
    3: "목요일",
    4: "금요일",
    5: "토요일",
    6: "일요일"
}

df["요일"] = df["급식일"].dt.dayofweek.map(
    weekday_map
)


# =========================================================
# 10. 월요일~금요일만 분석
# =========================================================

weekday_order = [
    "월요일",
    "화요일",
    "수요일",
    "목요일",
    "금요일"
]

df_weekday = df[
    df["요일"].isin(weekday_order)
].copy()


# =========================================================
# 11. NTR_INFO에서 단백질 함량 추출
# =========================================================

def extract_protein(ntr_info):
    """
    나이스의 NTR_INFO에서
    '단백질(g) : 숫자' 부분을 찾아 숫자만 가져옵니다.

    예:
    단백질(g) : 31.7
    → 31.7
    """

    # 데이터가 없는 경우
    if pd.isna(ntr_info):
        return None

    text = str(ntr_info)

    # 실제 나이스 응답 예:
    #
    # 탄수화물(g) : 79.4<br/>
    # 단백질(g) : 31.7<br/>
    # 지방(g) : 32.5
    #
    # 여기서 31.7만 추출합니다.

    match = re.search(
        r"단백질\s*\(g\)\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        text
    )

    if match:

        return float(
            match.group(1)
        )

    return None


# NTR_INFO가 있는지 확인
if "NTR_INFO" in df_weekday.columns:

    df_weekday["단백질(g)"] = (
        df_weekday["NTR_INFO"]
        .apply(extract_protein)
    )

else:

    df_weekday["단백질(g)"] = None


# =========================================================
# 12. 단백질 확인 가능 급식만 추출
# =========================================================

protein_df = df_weekday.dropna(
    subset=["단백질(g)"]
).copy()


# =========================================================
# 13. 전체 급식 일수와 단백질 확인 일수
# =========================================================

total_meal_days = len(df_weekday)

protein_meal_days = len(protein_df)


# =========================================================
# 14. 단백질 데이터가 하나도 없는 경우
# =========================================================

if protein_meal_days == 0:

    st.warning(
        "현재 나이스 급식식단정보에서 제공되는 데이터에는 "
        "단백질 함량이 없어 요일별 단백질 분석을 할 수 없습니다."
    )

else:

    # =====================================================
    # 15. 요일별 평균 단백질 계산
    # =====================================================

    weekday_average = (
        protein_df
        .groupby("요일", as_index=False)["단백질(g)"]
        .mean()
    )

    # 월요일 → 금요일 순서로 정렬
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


    # =====================================================
    # 16. 분석 결과 숫자 표시
    # =====================================================

    st.subheader("📊 분석 결과")

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "전체 급식 일수",
            f"{total_meal_days}일"
        )

    with col2:

        st.metric(
            "단백질 함량 확인 가능 급식 일수",
            f"{protein_meal_days}일"
        )


    # =====================================================
    # 17. 요일별 평균 단백질 막대그래프
    # =====================================================

    st.subheader(
        "🥩 요일별 평균 단백질 함량"
    )

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

        title=(
            "송탄고등학교 요일별 "
            "평균 단백질 함량"
        )
    )


    # 막대 위에 평균 단백질 값을 표시
    fig.update_traces(
        texttemplate="%{text:.1f} g",
        textposition="outside",

        hovertemplate=(
            "<b>%{x}</b><br>"
            "평균 단백질 함량: %{y:.1f} g"
            "<extra></extra>"
        )
    )


    # 그래프 설정
    fig.update_layout(
        xaxis_title="요일",
        yaxis_title="평균 단백질 함량 (g)",

        yaxis=dict(
            rangemode="tozero"
        ),

        uniformtext_minsize=10,
        uniformtext_mode="hide",

        margin=dict(
            t=70,
            b=50,
            l=60,
            r=30
        )
    )


    # 그래프 출력
    st.plotly_chart(
        fig,
        use_container_width=True
    )


    # =====================================================
    # 18. 가장 평균 단백질 함량이 높은 요일 찾기
    # =====================================================

    highest_row = weekday_average.loc[
        weekday_average["단백질(g)"].idxmax()
    ]

    highest_weekday = highest_row["요일"]

    highest_protein = highest_row["단백질(g)"]


    # =====================================================
    # 19. 그래프 아래 한 문장 설명
    # =====================================================

    st.info(
        "이 그래프로 알 수 있는 것: "
        f"송탄고등학교는 평균적으로 "
        f"{highest_weekday}에 단백질이 가장 많이 "
        "포함된 급식을 제공합니다."
    )


# =========================================================
# 20. 선택한 기간의 중식 메뉴
# =========================================================

st.subheader(
    "🍱 선택한 기간의 송탄고등학교 중식"
)


# 필요한 정보만 선택
menu_df = df[
    [
        "급식일",
        "요일",
        "DDISH_NM",
        "CAL_INFO"
    ]
].copy()


# 날짜를 보기 좋은 형태로 변환
menu_df["급식일"] = menu_df[
    "급식일"
].dt.strftime("%Y-%m-%d")


# 컬럼 이름을 한국어로 변경
menu_df = menu_df.rename(
    columns={
        "급식일": "급식일",
        "요일": "요일",
        "DDISH_NM": "중식 메뉴",
        "CAL_INFO": "칼로리"
    }
)


# 날짜가 빠른 순서로 정렬
menu_df = menu_df.sort_values(
    "급식일"
).reset_index(drop=True)


# =========================================================
# 21. 메뉴의 <br/>을 실제 줄바꿈으로 변환
# =========================================================

menu_df["중식 메뉴"] = (
    menu_df["중식 메뉴"]
    .astype(str)
    .str.replace(
        "<br/>",
        "\n",
        regex=False
    )
    .str.replace(
        "<br>",
        "\n",
        regex=False
    )
)


# =========================================================
# 22. 메뉴 표 표시
# =========================================================

st.dataframe(
    menu_df,
    use_container_width=True,
    hide_index=True,

    column_config={

        "급식일": st.column_config.TextColumn(
            "급식일",
            width="small"
        ),

        "요일": st.column_config.TextColumn(
            "요일",
            width="small"
        ),

        "중식 메뉴": st.column_config.TextColumn(
            "중식 메뉴",
            width="large"
        ),

        "칼로리": st.column_config.TextColumn(
            "칼로리",
            width="small"
        )
    }
)


# =========================================================
# 23. 데이터 출처 안내
# =========================================================

st.caption(
    "데이터 출처: 나이스 교육정보 개방 포털 "
    "급식식단정보 API"
)
