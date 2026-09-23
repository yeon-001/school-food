import streamlit as st
import requests
import pandas as pd
import re
import time
from datetime import date, timedelta


# =========================================================
# 기본 설정
# =========================================================
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


SCHOOL_API = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API = "https://open.neis.go.kr/hub/mealServiceDietInfo"

START_DATE = date(2026, 3, 4)
END_DATE = date(2026, 9, 23)


# =========================================================
# 인증키
# =========================================================
# Streamlit Cloud에서 Secrets에
#
# NEIS_KEY = "발급받은 인증키"
#
# 를 넣으면 사용합니다.
#
# 인증키가 없으면 NEIS가 제공하는 샘플 호출 방식으로 시도합니다.
try:
    NEIS_KEY = st.secrets.get("NEIS_KEY", "")
except Exception:
    NEIS_KEY = ""


# =========================================================
# 학교 검색
# =========================================================
@st.cache_data(ttl=600)
def search_school(keyword):

    params = {
        "Type": "json",
        "SCHUL_NM": keyword,
        "pIndex": 1,
        "pSize": 100
    }

    if NEIS_KEY:
        params["KEY"] = NEIS_KEY

    try:
        response = requests.get(
            SCHOOL_API,
            params=params,
            timeout=15
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
        return rows, "OK"

    except (KeyError, IndexError, TypeError):
        return [], "NO_DATA"


# =========================================================
# 학교 이름 줄임말 보정
# =========================================================
def expand_school_name(keyword):

    keyword = keyword.strip()

    # 수도여고 → 수도여자고등학교
    if keyword.endswith("여고"):
        return keyword[:-2] + "여자고등학교"

    # 서울고 → 서울고등학교
    if keyword.endswith("고") and not keyword.endswith("고등학교"):
        return keyword[:-1] + "고등학교"

    return keyword


# ====================================================
