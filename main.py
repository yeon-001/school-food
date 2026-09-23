import streamlit as st
import requests
import pandas as pd
import re
from datetime import date

# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="학교 급식 국 종류 분석",
    page_icon="🍲",
    layout="wide"
)

st.title("학교 급식 국 종류 분석")

st.write(
    "학교를 검색하고 선택하면 2026년 3월 4일부터 9월 23일까지 "
    "그 학교 급식표에 나온 국 종류의 횟수를 분석합니다."
)

# --------------------------------------------------
# 설정
# --------------------------------------------------

SCHOOL_API = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API = "https://open.neis.go.kr/hub/mealServiceDietInfo"

START_DATE = date(2026, 3, 4)
END_DATE = date(2026, 9, 23)

# Streamlit Cloud의 Secrets에서 NEIS_KEY를 가져옴
NEIS_KEY = st.secrets.get("NEIS_KEY", "")

# --------------------------------------------------
# 학교 이름 검색
# --------------------------------------------------

def search_school(keyword):
    """학교 이름으로 학교를 검색한다."""

    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": keyword
    }

    if NEIS_KEY:
        params["KEY"] = NEIS_KEY

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


# --------------------------------------------------
# 학교 이름 확장 검색
# --------------------------------------------------

def get_search_keywords(keyword):
    """학교 이름을 여러 형태로 검색한다."""

    keywords = [keyword]

    # 여고 → 여자고등학교
    if "여고" in keyword:
        keywords.append(
            keyword.replace("여고", "여자고등학교")
        )

    # 고 → 고등학교
    if keyword.endswith("고"):
        keywords.append(
            keyword[:-1] + "고등학교"
        )

    # 중 → 중학교
    if keyword.endswith("중"):
        keywords.append(
            keyword[:-1] + "중학교"
        )

    # 초 → 초등학교
    if keyword.endswith("초"):
        keywords.append(
            keyword[:-1] + "초등학교"
        )

    # 중복 제거
    return list(dict.fromkeys(keywords))


def search_school_with_fallback(keyword):
    """학교를 검색하고 필요하면 학교 이름을 확장해서 다시 검색한다."""

    all_results = []

    keywords = get_search_keywords(keyword)

    for word in keywords:
        results = search_school(word)

        for school in results:
            school_code = school.get("SD_SCHUL_CODE")

            # 같은 학교 중복 제거
            if not any(
                x.get("SD_SCHUL_CODE") == school_code
                for x in all_results
            ):
                all_results.append(school)

        if all_results:
            break

    return all_results


# --------------------------------------------------
# 급식 데이터 가져오기
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_meal_data(
    office_code,
    school_code,
    start_date,
    end_date
):
    """선택한 학교의 기간 내 점심 급식 데이터를 가져온다."""

    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": start_date.strftime("%Y%m%d"),
        "MLSV_TO_YMD": end_date.strftime("%Y%m%d")
    }

    if NEIS_KEY:
        params["KEY"] = NEIS_KEY

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


# --------------------------------------------------
# 급식 메뉴 정리
# --------------------------------------------------

def clean_menu_name(menu):
    """알레르기 번호와 불필요한 표시를 제거한다."""

    menu = str(menu)

    # HTML 줄바꿈 제거
    menu = re.sub(
        r"<br\s*/?>",
        "\n",
        menu,
        flags=re.IGNORECASE
    )

    # 괄호 안 내용 제거
    menu = re.sub(r"\([^)]*\)", "", menu)

    # 대괄호 안 내용 제거
    menu = re.sub(r"\[[^\]]*\]", "", menu)

    # 앞뒤 공백 제거
    menu = menu.strip()

    # 끝에 붙은 알레르기 번호 제거
    # 예: 미역국5.6.13.
    # 예: 김치찌개5.6.9
    menu = re.sub(
        r"(?:\d+\.)+\s*$",
        "",
        menu
    )

    menu = re.sub(
        r"(?:\d+\s*)+$",
        "",
        menu
    )

    # 별표 등의 표시 제거
    menu = menu.strip(" *·")

    # 여러 공백 하나로 정리
    menu = re.sub(r"\s+", " ", menu)

    return menu.strip()


# --------------------------------------------------
# 국 종류 판별
# --------------------------------------------------

def is_soup(menu):
    """국, 찌개, 탕, 전골 등의 메뉴인지 확인한다."""

    menu = clean_menu_name(menu)

    if not menu:
        return False

    soup_endings = [
        "국",
        "찌개",
        "탕",
        "전골"
    ]

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

    if any(menu.endswith(word) for word in soup_endings):
        return True

    if menu in soup_names:
        return True

    return False


# --------------------------------------------------
# 국 종류 분석
# --------------------------------------------------

def analyze_soups(meal_rows):
    """급식 데이터에서 국 종류별 등장 횟수를 계산한다."""

    soup_list = []

    for row in meal_rows:

        # 점심 데이터만 사용
        if str(row.get("MMEAL_SC_CODE", "2")) != "2":
            continue

        menu_text = row.get("DDISH_NM", "")

        if not menu_text:
            continue

        # <br> 기준으로 각각의 메뉴 분리
        menus = re.split(
            r"<br\s*/?>",
            menu_text,
            flags=re.IGNORECASE
        )

        for menu in menus:

            menu = clean_menu_name(menu)

            if is_soup(menu):
                soup_list.append(menu)

    if not soup_list:
        return pd.DataFrame(
            columns=["국 종류", "횟수"]
        )

    count_series = (
        pd.Series(soup_list)
        .value_counts()
        .sort_values(ascending=True)
    )

    result = pd.DataFrame({
        "국 종류": count_series.index,
        "횟수": count_series.values
    })

    return result


# --------------------------------------------------
# 학교 검색창
# --------------------------------------------------

st.subheader("🏫 학교 검색")

school_keyword = st.text_input(
    "학교 이름을 입력하세요",
    placeholder="예: 수도여고",
    key="school_search"
)

# --------------------------------------------------
# 학교 검색
# --------------------------------------------------

if school_keyword:

    with st.spinner("학교를 검색하고 있습니다..."):
        schools = search_school_with_fallback(
            school_keyword.strip()
        )

    if not schools:

        st.warning(
            "검색된 학교가 없습니다. 학교 이름을 다시 확인해 주세요."
        )

    else:

        st.success(
            f"{len(schools)}개의 학교를 찾았습니다."
        )

        # 학교 선택용 표시
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
            "분석할 학교를 선택하세요",
            range(len(school_options)),
            format_func=lambda x: school_options[x]
        )

        selected_school = schools[selected_index]

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

        # --------------------------------------------------
        # 선택 학교 정보
        # --------------------------------------------------

        st.divider()

        st.subheader("📌 선택한 학교")

        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**학교명:** {school_name}")

        with col2:
            st.write(f"**지역:** {region}")

        st.info(
            "분석 기간: 2026년 3월 4일 ~ 2026년 9월 23일"
        )

        # --------------------------------------------------
        # 분석 버튼
        # --------------------------------------------------

        if st.button(
            "🍲 국 종류 분석하기",
            type="primary",
            use_container_width=True
        ):

            if not NEIS_KEY:
                st.warning(
                    "NEIS_KEY가 설정되지 않았습니다. "
                    "Streamlit Cloud의 Secrets에 NEIS_KEY를 등록해야 "
                    "2026년 전체 기간의 급식 데이터를 가져올 수 있습니다."
                )

            else:

                with st.spinner(
                    f"{school_name}의 급식 데이터를 분석하고 있습니다..."
                ):

                    meal_rows = get_meal_data(
                        office_code,
                        school_code,
                        START_DATE,
                        END_DATE
                    )

                if not meal_rows:

                    st.info(
                        "해당 기간에 급식 데이터가 없습니다."
                    )

                else:

                    soup_df = analyze_soups(
                        meal_rows
                    )

                    # --------------------------------------------------
                    # 분석 결과
                    # --------------------------------------------------

                    st.divider()

                    st.subheader(
                        "🍲 국 종류별 등장 횟수"
                    )

                    if soup_df.empty:

                        st.info(
                            "해당 기간의 급식표에서 "
                            "국·찌개·탕·전골 종류를 찾지 못했습니다."
                        )

                    else:

                        # 가장 많이 나온 국
                        top_soup = soup_df.iloc[-1]

                        col1, col2 = st.columns(2)

                        with col1:
                            st.metric(
                                "가장 많이 나온 국",
                                top_soup["국 종류"]
                            )

                        with col2:
                            st.metric(
                                "등장 횟수",
                                f"{int(top_soup['횟수'])}회"
                            )

                        # --------------------------------------------------
                        # 막대그래프
                        # --------------------------------------------------

                        chart_df = soup_df.copy()

                        chart_df = chart_df.sort_values(
                            "횟수",
                            ascending=True
                        )

                        st.bar_chart(
                            chart_df.set_index("국 종류")[
                                ["횟수"]
                            ],
                            use_container_width=True
                        )

                        # --------------------------------------------------
                        # 표
                        # --------------------------------------------------

                        st.subheader(
                            "📋 국 종류별 횟수"
                        )

                        display_df = soup_df.sort_values(
                            "횟수",
                            ascending=False
                        ).reset_index(drop=True)

                        display_df.index = display_df.index + 1

                        st.dataframe(
                            display_df,
                            use_container_width=True
                        )
