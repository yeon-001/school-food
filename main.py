```python
import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import re


# ---------------------------------------
# 기본 설정
# ---------------------------------------
st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍱",
    layout="centered"
)

st.title("학교 급식 찾아보기")
st.write("학교 이름을 검색하고 원하는 날짜의 중식 메뉴를 확인해 보세요.")


SCHOOL_API = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# ---------------------------------------
# 한국 시간 기준 오늘 날짜
# ---------------------------------------
KST = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(KST).date()


# ---------------------------------------
# 학교 이름 검색어 보정
# ---------------------------------------
def expand_school_name(keyword):
    """
    짧게 입력한 학교 이름을 한 번 더 검색하기 위한 함수.

    예:
    수도여고 → 수도여자고등학교
    서울고 → 서울고등학교
    """

    expanded = keyword.strip()

    # '여고'를 '여자고등학교'로 변경
    expanded = re.sub(r"여고$", "여자고등학교", expanded)

    # '고'로 끝나는 경우 '고등학교'로 변경
    # 단, 이미 '고등학교'로 끝나면 변경하지 않음
    if expanded.endswith("고") and not expanded.endswith("고등학교"):
        expanded = expanded[:-1] + "고등학교"

    return expanded


# ---------------------------------------
# 학교 정보 API
# ---------------------------------------
@st.cache_data(ttl=600)
def search_school(keyword):
    """학교 이름으로 학교 정보를 검색한다."""

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
        return None, "NETWORK_ERROR"

    except ValueError:
        return None, "INVALID_RESPONSE"

    # 조회 결과가 없는 경우
    try:
        result_code = data["schoolInfo"][0]["head"][1]["RESULT"]["CODE"]

        if result_code == "INFO-200":
            return [], "NO_DATA"

    except (KeyError, IndexError, TypeError):
        pass

    # 학교 목록 가져오기
    try:
        rows = data["schoolInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return [], "NO_DATA"

    return rows, "OK"


# ---------------------------------------
# 급식 API
# ---------------------------------------
@st.cache_data(ttl=300)
def get_meal(atpt_code, school_code, date_string):
    """
    선택한 학교의 특정 날짜 중식을 가져온다.
    인증키 없이 사용할 경우 첫 5건만 반환될 수 있으므로
    조회 날짜를 하루로 제한한다.
    """

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
        return None, "NETWORK_ERROR"

    except ValueError:
        return None, "INVALID_RESPONSE"

    # 데이터가 없는 경우
    try:
        result_code = data["mealServiceDietInfo"][0]["head"][1]["RESULT"]["CODE"]

        if result_code == "INFO-200":
            return [], "NO_DATA"

    except (KeyError, IndexError, TypeError):
        pass

    # 급식 데이터 가져오기
    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return [], "NO_DATA"

    return rows, "OK"


# ---------------------------------------
# 학교 검색
# ---------------------------------------
school_keyword = st.text_input(
    "학교 이름",
    placeholder="예: 수도여고, 수도여자고등학교"
)

schools = []

if school_keyword.strip():

    # 먼저 사용자가 입력한 이름 그대로 검색
    schools, status = search_school(school_keyword.strip())

    # 못 찾았을 경우 이름을 풀어서 다시 검색
    if status == "NO_DATA" or not schools:

        expanded_keyword = expand_school_name(school_keyword.strip())

        # 실제로 검색어가 달라진 경우에만 다시 검색
        if expanded_keyword != school_keyword.strip():
            schools, status = search_school(expanded_keyword)

            if schools:
                st.info(
                    f"입력한 이름을 '{expanded_keyword}'로 바꾸어 다시 검색했습니다."
                )

    if status == "NETWORK_ERROR":
        st.error("학교 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")

    elif status == "INVALID_RESPONSE":
        st.error("학교 정보 API에서 올바른 응답을 받지 못했습니다.")

    elif not schools:
        st.info(
            "학교를 찾지 못했습니다. 학교 이름을 다시 확인해 주세요."
        )


# ---------------------------------------
# 학교 선택
# ---------------------------------------
if schools:

    # 같은 학교가 중복으로 오는 경우 제거
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
        school_name = school.get("SCHUL_NM", "")
        region = school.get("LCTN_SC_NM", "")
        return f"{school_name} ({region})"

    selected_school = st.selectbox(
        "학교를 선택하세요",
        unique_schools,
        format_func=school_label
    )


    # ---------------------------------------
    # 날짜 선택
    # ---------------------------------------
    selected_date = st.date_input(
        "급식 날짜",
        value=today_kst,
        format="YYYY-MM-DD"
    )

    date_string = selected_date.strftime("%Y%m%d")


    # ---------------------------------------
    # 급식 조회
    # ---------------------------------------
    if st.button("급식 찾아보기", type="primary", use_container_width=True):

        atpt_code = selected_school.get("ATPT_OFCDC_SC_CODE")
        school_code = selected_school.get("SD_SCHUL_CODE")

        meal_rows, meal_status = get_meal(
            atpt_code,
            school_code,
            date_string
        )

        if meal_status == "NETWORK_ERROR":
            st.error(
                "급식 정보를 불러오지 못했습니다. "
                "잠시 후 다시 시도해 주세요."
            )

        elif meal_status == "INVALID_RESPONSE":
            st.error(
                "급식 API에서 올바른 응답을 받지 못했습니다."
            )

        elif not meal_rows:
            st.info(
                f"{selected_date.strftime('%Y년 %m월 %d일')}에는 "
                "등록된 중식 급식이 없습니다."
            )

        else:
            # 선택 날짜의 중식만 찾기
            target_meal = None

            for meal in meal_rows:
                if meal.get("MLSV_YMD") == date_string:
                    target_meal = meal
                    break

            if target_meal is None:
                st.info(
                    f"{selected_date.strftime('%Y년 %m월 %d일')}에는 "
                    "등록된 중식 급식이 없습니다."
                )

            else:
                st.divider()

                st.subheader(
                    f"🍱 {selected_school.get('SCHUL_NM', '')}"
                )

                st.write(
                    f"📅 {selected_date.strftime('%Y년 %m월 %d일')} 중식"
                )

                # 메뉴
                menu_text = target_meal.get("DDISH_NM", "")

                # <br/> 태그를 줄바꿈으로 변경
                menu_text = re.sub(
                    r"<br\s*/?>",
                    "\n",
                    menu_text,
                    flags=re.IGNORECASE
                )

                # HTML 태그가 혹시 남아 있다면 제거
                menu_text = re.sub(
                    r"<[^>]+>",
                    "",
                    menu_text
                )

                menu_items = [
                    item.strip()
                    for item in menu_text.split("\n")
                    if item.strip()
                ]

                st.markdown("### 🍚 오늘의 메뉴")

                for item in menu_items:
                    st.write(f"• {item}")

                # 칼로리
                cal_info = target_meal.get("CAL_INFO", "")

                if cal_info:
                    st.markdown("### 🔥 칼로리")
                    st.write(cal_info)

                # 원본 메뉴도 접어서 확인할 수 있도록 제공
                with st.expander("원래 메뉴 데이터 보기"):
                    st.code(target_meal.get("DDISH_NM", ""))

else:
    st.info(
        "위에 학교 이름을 입력하면 학교를 선택할 수 있습니다."
    )
```
