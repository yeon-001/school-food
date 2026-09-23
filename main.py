import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------
# 페이지 설정
# ---------------------------------------
st.set_page_config(
    page_title="학교 급식 국 종류 분석",
    page_icon="🍲",
    layout="centered"
)

st.title("학교 급식 국 종류 분석")
st.write("학교를 선택하고 급식표에서 가장 많이 나온 국 종류를 알아보세요.")


SCHOOL_API = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API = "https://open.neis.go.kr/hub/mealServiceDietInfo"

KST = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(KST).date()


# ---------------------------------------
# 학교 이름 보정
# ---------------------------------------
def expand_school_name(keyword):
    keyword = keyword.strip()

    # 수도여고 → 수도여자고등학교
    if keyword.endswith("여고"):
        keyword = keyword[:-2] + "여자고등학교"

    # 서울고 → 서울고등학교
    elif keyword.endswith("고") and not keyword.endswith("고등학교"):
        keyword = keyword[:-1] + "고등학교"

    return keyword


# ---------------------------------------
# 학교 검색
# ---------------------------------------
@st.cache_data(ttl=600)
def search_school(keyword):

    params = {
        "Type": "json",
        "SCHUL_NM": keyword
    }

    try:
        response = requests.get(
            SCHOOL_API,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

    except requests.RequestException:
        return [], "NETWORK_ERROR"

    except ValueError:
        return [], "INVALID_RESPONSE"

    # 검색 결과 없음
    try:
        result_code = data["schoolInfo"][0]["head"][1]["RESULT"]["CODE"]

        if result_code == "INFO-200":
            return [], "NO_DATA"

    except (KeyError, IndexError, TypeError):
        pass

    try:
        rows = data["schoolInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return [], "NO_DATA"

    return rows, "OK"


# ---------------------------------------
# 하루 급식 조회
# ---------------------------------------
@st.cache_data(ttl=600)
def get_meal_for_day(atpt_code, school_code, date_string):

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": date_string,
        "MLSV_TO_YMD": date_string
    }

    try:
        response = requests.get(
            MEAL_API,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

    except requests.RequestException:
        return [], "NETWORK_ERROR"

    except ValueError:
        return [], "INVALID_RESPONSE"

    # 해당 날짜 급식 없음
    try:
        result_code = data["mealServiceDietInfo"][0]["head"][1]["RESULT"]["CODE"]

        if result_code == "INFO-200":
            return [], "NO_DATA"

    except (KeyError, IndexError, TypeError):
        pass

    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return [], "NO_DATA"

    return rows, "OK"


# ---------------------------------------
# 메뉴에서 알레르기 번호 제거
# ---------------------------------------
def clean_menu(menu):

    # <br/> → 줄바꿈
    menu = re.sub(
        r"<br\s*/?>",
        "\n",
        menu,
        flags=re.IGNORECASE
    )

    # HTML 태그 제거
    menu = re.sub(r"<[^>]+>", "", menu)

    # 알레르기 번호 제거
    # 예: 미역국(5.6.13) → 미역국
    menu = re.sub(
        r"\s*\(\s*\d+(?:\.\d+)*(?:\s*,\s*\d+(?:\.\d+)*)*\s*\)",
        "",
        menu
    )

    return menu


# ---------------------------------------
# 국 종류인지 판별
# ---------------------------------------
def is_soup(menu):

    menu = menu.strip()

    # 메뉴 끝의 괄호 등을 정리
    menu = re.sub(r"\s+", "", menu)

    # 국 종류로 볼 메뉴
    soup_keywords = [
        "국",
        "탕",
        "찌개",
        "전골"
    ]

    return any(menu.endswith(keyword) for keyword in soup_keywords)


# ---------------------------------------
# 학교 검색 입력
# ---------------------------------------
school_keyword = st.text_input(
    "학교 이름",
    placeholder="예: 수도여고, 수도여자고등학교"
)

schools = []

if school_keyword.strip():

    # 1차: 입력한 이름 그대로 검색
    schools, status = search_school(
        school_keyword.strip()
    )

    # 2차: 줄임말을 풀어서 검색
    if not schools:

        expanded_keyword = expand_school_name(
            school_keyword.strip()
        )

        if expanded_keyword != school_keyword.strip():

            schools, status = search_school(
                expanded_keyword
            )

            if schools:
                st.info(
                    f"'{school_keyword.strip()}'을(를) "
                    f"'{expanded_keyword}'로 바꾸어 다시 검색했습니다."
                )

    if status == "NETWORK_ERROR":
        st.error(
            "학교 정보를 불러오지 못했습니다. "
            "잠시 후 다시 시도해 주세요."
        )

    elif status == "INVALID_RESPONSE":
        st.error(
            "학교 정보 API에서 올바른 응답을 받지 못했습니다."
        )

    elif not schools:
        st.info(
            "학교를 찾지 못했습니다. 학교 이름을 다시 입력해 주세요."
        )


# ---------------------------------------
# 학교 선택
# ---------------------------------------
if schools:

    # 중복 학교 제거
    unique_schools = []
    seen = set()

    for school in schools:

        key = (
            school.get("ATPT_OFCDC_SC_CODE", ""),
            school.get("SD_SCHUL_CODE", "")
        )

        if key not in seen:
            seen.add(key)
            unique_schools.append(school)

    def school_label(school):
        return (
            f"{school.get('SCHUL_NM', '')} "
            f"({school.get('LCTN_SC_NM', '')})"
        )

    selected_school = st.selectbox(
        "학교를 선택하세요",
        unique_schools,
        format_func=school_label
    )


    # ---------------------------------------
    # 조회 기간
    # ---------------------------------------
    st.subheader("급식 조회 기간")

    default_start = today_kst - timedelta(days=29)

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "시작 날짜",
            value=default_start,
            max_value=today_kst,
            format="YYYY-MM-DD"
        )

    with col2:
        end_date = st.date_input(
            "끝 날짜",
            value=today_kst,
            max_value=today_kst,
            format="YYYY-MM-DD"
        )


    # ---------------------------------------
    # 분석 버튼
    # ---------------------------------------
    if st.button(
        "국 종류 분석하기",
        type="primary",
        use_container_width=True
    ):

        if start_date > end_date:
            st.error(
                "시작 날짜가 끝 날짜보다 늦을 수 없습니다."
            )
            st.stop()

        # 너무 긴 기간 방지
        total_days = (end_date - start_date).days + 1

        if total_days > 366:
            st.warning(
                "한 번에 최대 1년까지 조회할 수 있습니다."
            )
            st.stop()

        atpt_code = selected_school.get(
            "ATPT_OFCDC_SC_CODE"
        )

        school_code = selected_school.get(
            "SD_SCHUL_CODE"
        )

        all_menu = []

        progress = st.progress(0)
        status_text = st.empty()

        current_date = start_date

        success_count = 0
        error_count = 0

        for i in range(total_days):

            date_string = current_date.strftime("%Y%m%d")

            status_text.write(
                f"급식 정보를 가져오는 중... "
                f"{i + 1} / {total_days}"
            )

            rows, meal_status = get_meal_for_day(
                atpt_code,
                school_code,
                date_string
            )

            if meal_status == "NETWORK_ERROR":
                error_count += 1

            elif meal_status == "INVALID_RESPONSE":
                error_count += 1

            elif rows:

                success_count += 1

                for row in rows:

                    menu_text = row.get(
                        "DDISH_NM",
                        ""
                    )

                    menu_text = clean_menu(menu_text)

                    menu_items = [
                        item.strip()
                        for item in menu_text.split("\n")
                        if item.strip()
                    ]

                    for menu in menu_items:

                        if is_soup(menu):

                            all_menu.append({
                                "날짜": current_date,
                                "국": menu
                            })

            current_date += timedelta(days=1)

            progress.progress(
                (i + 1) / total_days
            )

        progress.empty()
        status_text.empty()


        # ---------------------------------------
        # 결과
        # ---------------------------------------
        st.divider()

        if not all_menu:

            st.info(
                "선택한 기간에 분석할 국 종류가 없습니다."
            )

        else:

            df = pd.DataFrame(all_menu)

            soup_counts = (
                df["국"]
                .value_counts()
                .sort_values(ascending=False)
            )

            result_df = soup_counts.reset_index()

            result_df.columns = [
                "국 이름",
                "횟수"
            ]


            # ---------------------------------------
            # 가장 많이 나온 국
            # ---------------------------------------
            top_soup = result_df.iloc[0]

            st.subheader("🍲 가장 많이 나온 국")

            st.metric(
                label="국 이름",
                value=top_soup["국 이름"],
                delta=f"{int(top_soup['횟수'])}회"
            )


            # ---------------------------------------
            # 막대 그래프
            # ---------------------------------------
            st.subheader("📊 국 종류별 등장 횟수")

            # 횟수가 많은 순서로 그래프 표시
            chart_df = (
                result_df
                .set_index("국 이름")
            )

            st.bar_chart(
                chart_df["횟수"],
                height=500
            )


            # ---------------------------------------
            # 상세 표
            # ---------------------------------------
            st.subheader("국 종류별 횟수")

            display_df = result_df.copy()
            display_df.index = range(
                1,
                len(display_df) + 1
            )

            st.dataframe(
                display_df,
                use_container_width=True
            )


            # ---------------------------------------
            # 분석 정보
            # ---------------------------------------
            st.caption(
                f"분석 기간: "
                f"{start_date.strftime('%Y-%m-%d')} ~ "
                f"{end_date.strftime('%Y-%m-%d')}"
            )

            st.caption(
                f"급식이 확인된 날짜: {success_count}일"
            )

            if error_count > 0:
                st.caption(
                    f"일부 날짜는 API 응답 문제로 제외되었습니다: "
                    f"{error_count}일"
                )
