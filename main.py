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
st.write("학교 급식표에서 자주 나오는 국 종류를 찾아보세요.")

SCHOOL_API = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API = "https://open.neis.go.kr/hub/mealServiceDietInfo"

KST = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(KST).date()


# ---------------------------------------
# 학교 이름 줄임말 처리
# ---------------------------------------
def expand_school_name(keyword):
    keyword = keyword.strip()

    if keyword.endswith("여고"):
        return keyword[:-2] + "여자고등학교"

    if keyword.endswith("고") and not keyword.endswith("고등학교"):
        return keyword[:-1] + "고등학교"

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

    try:
        result_code = (
            data["schoolInfo"][0]
            ["head"][1]
            ["RESULT"]["CODE"]
        )

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
def get_meal_for_day(
    atpt_code,
    school_code,
    date_string
):

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",
        "MLSV_YMD": date_string,
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

    # 데이터 없음
    try:
        result_code = (
            data["mealServiceDietInfo"][0]
            ["head"][1]
            ["RESULT"]["CODE"]
        )

        if result_code == "INFO-200":
            return [], "NO_DATA"

    except (KeyError, IndexError, TypeError):
        pass

    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return [], "NO_DATA"

    return
