import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO

# ==========================================
# [1] 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="서주사이언티픽 최저가 검색 시스템",
    page_icon="🧬",
    layout="wide"
)

# ==========================================
# [2] 보안(로그인) 기능
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("")
        st.markdown("### 🧬 서주사이언티픽 최저가 검색 시스템")
        st.info("인가된 연구원만 접속할 수 있습니다.")
        password = st.text_input("접속 코드를 입력하세요", type="password")
        
        if st.button("시스템 접속"):
            if password == st.secrets["access_code"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("⛔ 승인되지 않은 코드입니다.")
    return False

if not check_password():
    st.stop()

# ==========================================
# 👇 메인 기능 시작
# ==========================================

CLIENT_ID = "SWML8CniVRJyDPKSeIkt"     # 본인 키 확인
CLIENT_SECRET = "C_U15jOct2"           # 본인 키 확인

def get_naver_price(keyword):
    """ 네이버 쇼핑 API 검색 """
    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
    params = {"query": keyword, "display": 1, "sort": "asc"} # 정확도순이 아닌 '가격오름차순(asc)'
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            items = data.get('items')
            if items:
                title = items[0]['title'].replace('<b>', '').replace('</b>', '')
                price = int(items[0]['lprice'])
                link = items[0]['link']
                return title, price, link
            else:
                return "검색결과없음", 0, ""
        else:
            return f"오류({response.status_code})", 0, ""
    except Exception as e:
        return f"통신에러:{str(e)}", 0, ""

# -----------------------------------------------------------
# [핵심] 스마트 컬럼 감지 함수
# -----------------------------------------------------------
def find_column(columns, keywords):
    """주어진 키워드 리스트 중 하나라도 포함된 컬럼명을 찾아 반환"""
    for col in columns:
        col_str = str(col).replace(" ", "").lower() # 공백제거, 소문자 변환 후 비교
        for key in keywords:
            if key in col_str:
                return col
    return None

# UI 구성
st.title("🔎 스마트 최저가 검색 (정밀검색 버전)")
st.markdown("---")
st.markdown("""
**💡 업그레이드된 기능:**
* **'제조사', '모델명', '상품명', '규격'**을 자동으로 찾아 조합합니다.
* 정보가 많을수록 더 정확한 최저가를 찾아냅니다.
""")

uploaded_file = st.file_uploader("엑셀 파일 업로드 (.xlsx)", type=['xlsx'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        st.write("📂 **데이터 미리보기**")
        st.dataframe(df.head(3))
        
        # -------------------------------------------------------
        # 🧠 스마트 컬럼 매핑 로직
        # -------------------------------------------------------
        st.subheader("🛠️ 검색 조건 자동 설정")
        cols = df.columns
        
        # 1. 각 정보를 담고 있을 법한 컬럼 찾기
        col_maker = find_column(cols, ['제조사', '브랜드', '메이커', 'brand', 'maker'])
        col_model = find_column(cols, ['모델', '모델명', 'model', 'cat', 'no'])
        col_name = find_column(cols, ['상품명', '품목명', '품명', 'description', 'name'])
        col_spec = find_column(cols, ['규격', '사양', 'size', 'spec'])
        
        # 상품명은 필수! 못 찾으면 강제로 지정
        if col_name is None: 
            col_name = cols[0] # 첫 번째 열을 상품명으로 가정

        # 매핑 결과 보여주기
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("제조사 열", col_maker if col_maker else "(없음)")
        c2.metric("모델명 열", col_model if col_model else "(없음)")
        c3.metric("상품명 열", col_name)
        c4.metric("규격 열", col_spec if col_spec else "(없음)")

        st.caption(f"👉 조합된 검색어 예시: **[{col_maker}] [{col_model}] [{col_name}] [{col_spec}]**")
        # -------------------------------------------------------

        if st.button("🚀 정밀 검색 시작", type="primary"):
            
            res_titles, res_prices, res_links, res_keywords = [], [], [], []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            total = len(df)
            
            for i, row in df.iterrows():
                # 검색어 조합하기 (값이 있는 것만 합침)
                keywords = []
                
                if col_maker and str(row[col_maker]) != 'nan': keywords.append(str(row[col_maker]))
                if col_model and str(row[col_model]) != 'nan': keywords.append(str(row[col_model]))
                if col_name  and str(row[col_name])  != 'nan': keywords.append(str(row[col_name]))
                if col_spec  and str(row[col_spec])  != 'nan': keywords.append(str(row[col_spec]))
                
                full_keyword = " ".join(keywords) # 띄어쓰기로 연결
                
                status_text.text(f"[{i+1}/{total}] 검색 중: {full_keyword}")
                
                # 네이버 검색 실행
                title, price, link = get_naver_price(full_keyword)
                
                res_titles.append(title)
                res_prices.append(price)
                res_links.append(link)
                res_keywords.append(full_keyword) # 실제로 검색한 단어도 기록
                
                progress_bar.progress((i + 1) / total)
                time.sleep(0.2) # API 보호용 딜레이
            
            # 결과 정리
            df['실제검색어'] = res_keywords
            df['네이버상품명'] = res_titles
            df['최저가'] = res_prices
            df['링크'] = res_links
            
            status_text.success("✅ 검색 완료!")
            st.dataframe(df)
            
            # 다운로드
            def convert_df(df):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                return output.getvalue()

            st.download_button(
                label="📥 결과 다운로드",
                data=convert_df(df),
                file_name='정밀검색결과.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )

    except Exception as e:
        st.error(f"오류 발생: {e}")
