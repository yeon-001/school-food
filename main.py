import streamlit as st
import requests
import pandas as pd
import re
import plotly.express as px
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍚",
    layout="wide"
)


# =========================================================
# 제목
# =========================================================

st.title("🍚 학교 급식 찾아보기")

st.write(
    "학교를 검색하고 날짜를 선택하면 그날의 중식 메뉴를 확인할 수 있습니다."
)


# =========================================================
# NEIS API
# =========================================================

SCHOOL_API = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# =========================================================
# 한국 시간
# =========================================================

KST = ZoneInfo("Asia/Seoul")

today_korea = datetime.now(KST).date()


# =========================================================
# 국 종류 분석 기간
# =========================================================

START_DATE = date(2026, 3, 4)
END_DATE = date(2026, 9, 23)


# =========================================================
# 학교 검색
# =========================================================

@st.cache_data(ttl=3600)
def search_school(keyword):

    params = {
        "Type": "json",
        "SCHUL_NM": keyword,
        "pIndex": 1,
        "pSize": 5
    }

    try:

        response = requests.get(
            SCHOOL_API,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if "schoolInfo" not in data:
            return []

        for item in data["schoolInfo"]:

            if "row" in item:
                return item["row"]

        return []

    except Exception:

        return []


# =========================================================
# 학교 검색어 확장
# =========================================================

def get_search_keywords(keyword):

    keywords = [keyword]

    # 여고 → 여자고등학교

    if "여고" in keyword:

        keywords.append(
            keyword.replace(
                "여고",
                "여자고등학교"
            )
        )

    # 마지막 글자가 고

    if keyword.endswith("고"):

        keywords.append(
            keyword[:-1] + "고등학교"
        )

    # 마지막 글자가 중

    if keyword.endswith("중"):

        keywords.append(
            keyword[:-1] + "중학교"
        )

    # 마지막 글자가 초

    if keyword.endswith("초"):

        keywords.append(
            keyword[:-1] + "초등학교"
        )

    return list(
        dict.fromkeys(keywords)
    )


# =========================================================
# 학교 검색 + 확장 검색
# =========================================================

def search_school_with_fallback(keyword):

    all_results = []

    search_keywords = get_search_keywords(keyword)

    for word in search_keywords:

        results = search_school(word)

        for school in results:

            school_code = school.get(
                "SD_SCHUL_CODE"
            )

            already_exists = any(
                x.get("SD_SCHUL_CODE") == school_code
                for x in all_results
            )

            if not already_exists:
                all_results.append(school)

        if all_results:
            break

    return all_results


# =========================================================
# 특정 날짜의 중식 가져오기
# =========================================================

@st.cache_data(ttl=3600)
def get_meal_data(
    office_code,
    school_code,
    selected_date
):

    params = {

        "Type": "json",

        "ATPT_OFCDC_SC_CODE":
            office_code,

        "SD_SCHUL_CODE":
            school_code,

        # 2 = 중식
        "MMEAL_SC_CODE":
            "2",

        "MLSV_FROM_YMD":
            selected_date.strftime("%Y%m%d"),

        "MLSV_TO_YMD":
            selected_date.strftime("%Y%m%d"),

        "pSize": 5,

        "pIndex": 1
    }

    try:

        response = requests.get(
            MEAL_API,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if "mealServiceDietInfo" not in data:
            return []

        for item in data["mealServiceDietInfo"]:

            if "row" in item:
                return item["row"]

        return []

    except Exception:

        return []


# =========================================================
# 여러 날의 급식 데이터 가져오기
# =========================================================

@st.cache_data(ttl=3600)
def get_meal_data_chunk(
    office_code,
    school_code,
    start_date,
    end_date
):

    params = {

        "Type": "json",

        "ATPT_OFCDC_SC_CODE":
            office_code,

        "SD_SCHUL_CODE":
            school_code,

        "MMEAL_SC_CODE":
            "2",

        "MLSV_FROM_YMD":
            start_date.strftime("%Y%m%d"),

        "MLSV_TO_YMD":
            end_date.strftime("%Y%m%d"),

        "pSize": 5,

        "pIndex": 1
    }

    try:

        response = requests.get(
            MEAL_API,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        if "mealServiceDietInfo" not in data:
            return []

        for item in data["mealServiceDietInfo"]:

            if "row" in item:
                return item["row"]

        return []

    except Exception:

        return []


# =========================================================
# 전체 기간 급식 데이터
# =========================================================

@st.cache_data(ttl=3600)
def get_all_meal_data(
    office_code,
    school_code,
    start_date,
    end_date
):

    all_rows = []

    current_start = start_date

    while current_start <= end_date:

        current_end = min(
            current_start + timedelta(days=4),
            end_date
        )

        rows = get_meal_data_chunk(
            office_code,
            school_code,
            current_start,
            current_end
        )

        all_rows.extend(rows)

        current_start = (
            current_end + timedelta(days=1)
        )

    # 중복 제거

    unique_rows = {}

    for row in all_rows:

        meal_date = row.get(
            "MLSV_YMD",
            ""
        )

        meal_code = row.get(
            "MMEAL_SC_CODE",
            "2"
        )

        key = (
            meal_date,
            meal_code
        )

        unique_rows[key] = row

    return list(unique_rows.values())


# =========================================================
# 원본 메뉴 표시
# =========================================================

def format_menu(menu_text):

    if not menu_text:
        return ""

    return re.sub(
        r"<br\s*/?>",
        "\n",
        menu_text,
        flags=re.IGNORECASE
    ).strip()


# =========================================================
# 국 이름 정리
# =========================================================

def clean_menu_name(menu):

    menu = str(menu)

    menu = re.sub(
        r"<br\s*/?>",
        " ",
        menu,
        flags=re.IGNORECASE
    )

    # 괄호 안 알레르기 번호 제거

    menu = re.sub(
        r"\([^)]*\)",
        "",
        menu
    )

    # 대괄호 제거

    menu = re.sub(
        r"\[[^\]]*\]",
        "",
        menu
    )

    # 5.6.13. 같은 알레르기 번호 제거

    menu = re.sub(
        r"(?:\d+\.)+\s*$",
        "",
        menu
    )

    # 끝의 숫자 제거

    menu = re.sub(
        r"(?:\d+\s*)+$",
        "",
        menu
    )

    menu = menu.strip()

    menu = menu.strip(" *·")

    menu = re.sub(
        r"\s+",
        " ",
        menu
    )

    return menu.strip()


# =========================================================
# 국인지 확인
# =========================================================

def is_soup(menu):

    menu = clean_menu_name(menu)

    if not menu:
        return False

    soup_endings = [
        "국",
        "찌개",
        "탕",
        "전골"
    ]

    for ending in soup_endings:

        if menu.endswith(ending):
            return True

    soup_names = [
        "육개장",
        "닭개장",
        "감자탕",
        "갈비탕",
        "곰탕",
        "설렁탕",
        "삼계탕",
        "추어탕",
        "도가니탕",
        "순대국",
        "순댓국"
    ]

    if menu in soup_names:
        return True

    return False


# =========================================================
# 국 종류 분석
# =========================================================

def analyze_soups(meal_rows):

    soup_list = []

    for row in meal_rows:

        meal_code = str(
            row.get(
                "MMEAL_SC_CODE",
                "2"
            )
        )

        if meal_code != "2":
            continue

        menu_text = row.get(
            "DDISH_NM",
            ""
        )

        if not menu_text:
            continue

        menus = re.split(
            r"<br\s*/?>",
            menu_text,
            flags=re.IGNORECASE
        )

        for menu in menus:

            menu = clean_menu_name(menu)

            if not menu:
                continue

            if is_soup(menu):

                soup_list.append(menu)

    if not soup_list:

        return pd.DataFrame(
            columns=[
                "국 종류",
                "횟수"
            ]
        )

    count_series = pd.Series(
        soup_list
    ).value_counts()

    result = pd.DataFrame({
        "국 종류": count_series.index,
        "횟수": count_series.values
    })

    return result


# =========================================================
# 학교 검색
# =========================================================

st.subheader("🏫 학교 검색")

school_keyword = st.text_input(
    "학교 이름을 입력하세요",
    placeholder="예: 수도여고"
)


# =========================================================
# 학교 검색 결과
# =========================================================

if school_keyword.strip():

    with st.spinner(
        "학교를 검색하고 있습니다..."
    ):

        schools = search_school_with_fallback(
            school_keyword.strip()
        )

    # =====================================================
    # 학교 없음
    # =====================================================

    if not schools:

        st.info(
            "🔎 검색된 학교가 없습니다. "
            "학교 이름을 다시 확인해 주세요."
        )

    # =====================================================
    # 학교 있음
    # =====================================================

    else:

        st.success(
            f"{len(schools)}개의 학교를 찾았습니다."
        )

        school_options = []

        for school in schools:

            school_name = school.get(
                "SCHUL_NM",
                "학교명 없음"
            )

            region = school.get(
                "LCTN_SC_NM",
                "지역 정보 없음"
            )

            school_options.append(
                f"{school_name} ({region})"
            )

        selected_index = st.selectbox(
            "학교를 선택하세요",
            range(len(school_options)),
            format_func=lambda x:
                school_options[x]
        )

        selected_school = schools[
            selected_index
        ]

        school_name = selected_school.get(
            "SCHUL_NM",
            ""
        )

        region = selected_school.get(
            "LCTN_SC_NM",
            ""
        )

        office_code = selected_school.get(
            "ATPT_OFCDC_SC_CODE",
            ""
        )

        school_code = selected_school.get(
            "SD_SCHUL_CODE",
            ""
        )

        # =================================================
        # 선택한 학교
        # =================================================

        st.divider()

        st.subheader(
            "📌 선택한 학교"
        )

        col1, col2 = st.columns(2)

        with col1:

            st.write(
                f"**학교명:** {school_name}"
            )

        with col2:

            st.write(
                f"**지역:** {region}"
            )

        # =================================================
        # 날짜별 급식
        # =================================================

        st.divider()

        st.header(
            "🍚 날짜별 급식 찾아보기"
        )

        selected_date = st.date_input(
            "급식 날짜를 선택하세요",
            value=today_korea
        )

        if st.button(
            "🍚 급식 확인하기",
            type="primary",
            use_container_width=True
        ):

            with st.spinner(
                "급식 정보를 가져오는 중입니다..."
            ):

                meal_rows = get_meal_data(
                    office_code,
                    school_code,
                    selected_date
                )

            if not meal_rows:

                st.info(
                    f"📭 "
                    f"{selected_date.strftime('%Y년 %m월 %d일')}에는 "
                    "등록된 중식 급식 정보가 없습니다."
                )

            else:

                lunch_row = None

                for row in meal_rows:

                    if str(
                        row.get(
                            "MMEAL_SC_CODE",
                            ""
                        )
                    ) == "2":

                        lunch_row = row
                        break

                if lunch_row is None:

                    st.info(
                        "등록된 중식 급식 정보가 없습니다."
                    )

                else:

                    st.subheader(
                        f"🍽️ "
                        f"{selected_date.strftime('%Y년 %m월 %d일')} 중식"
                    )

                    menu_text = lunch_row.get(
                        "DDISH_NM",
                        ""
                    )

                    calorie = lunch_row.get(
                        "CAL_INFO",
                        ""
                    )

                    # 메뉴

                    st.markdown(
                        "### 🍱 오늘의 메뉴"
                    )

                    if menu_text:

                        formatted_menu = format_menu(
                            menu_text
                        )

                        menu_items = formatted_menu.split(
                            "\n"
                        )

                        for menu in menu_items:

                            menu = menu.strip()

                            if menu:

                                st.write(
                                    f"• {menu}"
                                )

                    else:

                        st.info(
                            "메뉴 정보가 등록되어 있지 않습니다."
                        )

                    # 칼로리

                    st.markdown(
                        "### 🔥 칼로리"
                    )

                    if calorie:

                        st.write(calorie)

                    else:

                        st.info(
                            "칼로리 정보가 등록되어 있지 않습니다."
                        )

                    # 원본

                    with st.expander(
                        "📋 원본 메뉴 정보 보기"
                    ):

                        st.write(menu_text)

        # =================================================
        # 국 종류 분석
        # =================================================

        st.divider()

        st.header(
            "🍲 국 종류 분석"
        )

        st.write(
            "2026년 3월 4일부터 9월 23일까지 "
            "이 학교의 중식에 나온 국·찌개·탕·전골 종류를 분석합니다."
        )

        st.info(
            "📅 분석 기간: "
            "2026년 3월 4일 ~ 2026년 9월 23일"
        )

        if st.button(
            "🍲 국 종류 분석하기",
            type="secondary",
            use_container_width=True
        ):

            with st.spinner(
                f"{school_name}의 전체 급식 데이터를 분석하고 있습니다..."
            ):

                all_meal_rows = get_all_meal_data(
                    office_code,
                    school_code,
                    START_DATE,
                    END_DATE
                )

            if not all_meal_rows:

                st.info(
                    "해당 기간에 급식 데이터가 없습니다."
                )

            else:

                soup_df = analyze_soups(
                    all_meal_rows
                )

                if soup_df.empty:

                    st.info(
                        "해당 기간의 급식표에서 "
                        "국·찌개·탕·전골 종류를 찾지 못했습니다."
                    )

                else:

                    # =================================================
                    # 횟수 기준 내림차순
                    # =================================================

                    sorted_soup_df = (
                        soup_df
                        .sort_values(
                            by="횟수",
                            ascending=False,
                            kind="stable"
                        )
                        .reset_index(drop=True)
                    )

                    # =================================================
                    # 최대 횟수
                    # =================================================

                    max_count = int(
                        sorted_soup_df["횟수"].max()
                    )

                    # =================================================
                    # 공동 1위
                    # =================================================

                    top_soups = (
                        sorted_soup_df[
                            sorted_soup_df["횟수"] == max_count
                        ]["국 종류"]
                        .tolist()
                    )

                    # =================================================
                    # 결과 표시
                    # =================================================

                    col1, col2 = st.columns(2)

                    with col1:

                        st.metric(
                            "가장 많이 나온 국",
                            ", ".join(top_soups)
                        )

                    with col2:

                        st.metric(
                            "등장 횟수",
                            f"{max_count}회"
                        )

                    if len(top_soups) > 1:

                        st.info(
                            "🏆 공동 1위: "
                            + ", ".join(top_soups)
                            + f" ({max_count}회)"
                        )

                    # =================================================
                    # 그래프
                    # =================================================

                    st.subheader(
                        "📊 국 종류별 등장 횟수"
                    )

                    chart_df = (
                        sorted_soup_df.copy()
                    )

                    # -------------------------------------------------
                    # 그래프의 가로 길이
                    # -------------------------------------------------
                    #
                    # 국 종류가 많을수록 그래프를 넓게 만든다.
                    # 한 종류당 최소 70px 정도의 공간을 확보한다.
                    #
                    # 예:
                    # 10개 → 1,000px
                    # 30개 → 2,100px
                    # 50개 → 3,500px
                    #
                    # 따라서 한 화면에 억지로 전부 넣지 않고
                    # 가로로 넘겨 보면서 확인할 수 있다.
                    # -------------------------------------------------

                    number_of_soups = len(chart_df)

                    chart_width = max(
                        1200,
                        number_of_soups * 75
                    )

                    # -------------------------------------------------
                    # x축 순서를 직접 지정
                    # -------------------------------------------------

                    category_order = (
                        chart_df["국 종류"]
                        .tolist()
                    )

                    # -------------------------------------------------
                    # Plotly 그래프
                    # -------------------------------------------------

                    fig = px.bar(
                        chart_df,
                        x="국 종류",
                        y="횟수",
                        text="횟수",
                        title="국 종류별 등장 횟수"
                    )

                    # -------------------------------------------------
                    # 막대 위 숫자
                    # -------------------------------------------------

                    fig.update_traces(
                        textposition="outside",
                        cliponaxis=False
                    )

                    # -------------------------------------------------
                    # X축
                    # -------------------------------------------------

                    fig.update_xaxes(

                        title_text="국 종류",

                        # 글자를 가로로 표시
                        tickangle=0,

                        # 정렬 순서 고정
                        categoryorder="array",

                        categoryarray=category_order,

                        # 글자 크기
                        tickfont=dict(
                            size=12
                        ),

                        # 축 제목과 글자 사이 공간
                        automargin=True
                    )

                    # -------------------------------------------------
                    # Y축
                    # -------------------------------------------------

                    fig.update_yaxes(

                        title_text="횟수",

                        dtick=1,

                        rangemode="tozero",

                        tickfont=dict(
                            size=12
                        )
                    )

                    # -------------------------------------------------
                    # 그래프 전체
                    # -------------------------------------------------

                    fig.update_layout(

                        # 핵심:
                        # 국 종류가 많으면 그래프 자체를 넓게 만든다.
                        width=chart_width,

                        height=600,

                        margin=dict(
                            l=70,
                            r=40,
                            t=80,
                            b=150
                        ),

                        # 막대 사이 간격
                        bargap=0.25,

                        # x축 순서 다시 고정
                        xaxis=dict(
                            categoryorder="array",
                            categoryarray=category_order
                        )
                    )

                    # -------------------------------------------------
                    # 안내
                    # -------------------------------------------------

                    st.caption(
                        "💡 국 종류가 많아서 그래프를 넓게 만들었습니다. "
                        "아래 그래프를 좌우로 이동하면서 국 이름을 확인할 수 있습니다."
                    )

                    # -------------------------------------------------
                    # 그래프 출력
                    # -------------------------------------------------

                    st.plotly_chart(
                        fig,
                        use_container_width=False
                    )

                    # =================================================
                    # 표
                    # =================================================

                    st.subheader(
                        "📋 국 종류별 횟수"
                    )

                    display_df = (
                        sorted_soup_df.copy()
                    )

                    display_df.index = (
                        display_df.index + 1
                    )

                    st.dataframe(
                        display_df,
                        use_container_width=True
                    )
