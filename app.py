import streamlit as st

# [1] 페이지 기본 설정 (가장 윗줄에 있어야 함)
st.set_page_config(
    page_title="서주사이언티픽 최저가 검색 시스템",
    page_icon="🧬",
    layout="wide"
)

# [2] 비밀번호 체크 함수 (보안 게이트)
def check_password():
    """비밀번호가 맞으면 True, 아니면 False 반환"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # 로그인 화면 디자인
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("")
        st.write("")
        st.markdown("### 🧬 서주사이언티픽 최저가 검색 시스템")
        st.info("인가된 연구원만 접속할 수 있습니다.")
        
        password = st.text_input("접속 코드를 입력하세요", type="password")
        
        if st.button("시스템 접속"):
            # st.secrets에 저장된 비밀번호와 비교
            if password == st.secrets["access_code"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("⛔ 승인되지 않은 코드입니다.")
    return False

# [3] 보안 적용: 비밀번호 틀리면 여기서 코드 중단
if not check_password():
    st.stop()

# ==========================================
# 👇 여기 아래부터 기존에 만드신 최저가 검색 코드가 시작되면 됩니다.
# ==========================================

st.title("🔎 MRO 품목 최저가 검색")
st.markdown("---")
# (이하 기존 코드...)

import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO

# ==========================================
# [사용자 설정] 네이버 API 키 입력 (본인 키로 변경하세요!)
# ==========================================
CLIENT_ID = "SWML8CniVRJyDPKSeIkt"
CLIENT_SECRET = "C_U15jOct2"

# ------------------------------------------------------------------
# 0. 기본 설정
# ------------------------------------------------------------------
st.set_page_config(page_title="최저가 검색기", page_icon="🔍", layout="wide")

st.title("🛒 물품 최저가 자동 검색기")
st.markdown("""
**사용 방법:**
1. 엑셀 파일을 업로드합니다. (파일명은 상관없음)
2. **'상품명'**과 **'규격'** 컬럼이 있는지 확인합니다. (없으면 자동으로 C, D열을 읽습니다)
3. [검색 시작] 버튼을 누릅니다.
""")
st.divider()

# ------------------------------------------------------------------
# 1. 기능 함수 정의
# ------------------------------------------------------------------
def get_naver_price(keyword):
    """ 네이버 쇼핑 API 검색 """
    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
    params = {"query": keyword, "display": 1, "sort": "asc"}
    
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

# ------------------------------------------------------------------
# 2. 메인 화면 로직
# ------------------------------------------------------------------
uploaded_file = st.file_uploader("엑셀 파일 업로드 (.xlsx)", type=['xlsx'])

if uploaded_file:
    try:
        # 엑셀 읽기
        df = pd.read_excel(uploaded_file)
        
        st.write("📂 **업로드된 데이터 확인 (상위 5개)**")
        st.dataframe(df.head())
        
        col_count = len(df)
        st.info(f"총 {col_count}개의 품목을 찾았습니다.")

        # -------------------------------------------------------
        # [중요] 어떤 열(Column)을 읽을지 결정하는 로직
        # -------------------------------------------------------
        name_col = None
        spec_col = None

        # 1. '상품명', '품목명' 같은 이름이 있는지 찾기
        for col in df.columns:
            if "상품명" in str(col) or "품목명" in str(col):
                name_col = col
            if "규격" in str(col):
                spec_col = col
        
        # 2. 이름으로 못 찾았으면 강제로 C열(2번째), D열(3번째) 지정
        if name_col is None: name_col = df.columns[2] # C열
        if spec_col is None: spec_col = df.columns[3] # D열

        st.success(f"✅ 검색 기준: **'{name_col}'** + **'{spec_col}'**")
        # -------------------------------------------------------

        if st.button("🚀 최저가 검색 시작 (Click!)", type="primary"):
            
            res_titles, res_prices, res_links = [], [], []
            
            # 진행률 바
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, row in df.iterrows():
                # 데이터 가져오기
                p_name = str(row[name_col])
                p_spec = str(row[spec_col])
                
                # 'nan' (비어있음) 처리
                if p_name == 'nan': p_name = ""
                if p_spec == 'nan': p_spec = ""
                
                search_key = f"{p_name} {p_spec}"
                
                # 상태 메시지
                status_text.text(f"[{i+1}/{col_count}] 검색 중... {search_key}")
                
                # 검색 실행
                title, price, link = get_naver_price(search_key)
                
                res_titles.append(title)
                res_prices.append(price)
                res_links.append(link)
                
                # 진행률 업데이트
                progress_bar.progress((i + 1) / col_count)
                time.sleep(0.3) # 0.3초 대기
            
            # 결과 저장
            df['네이버상품명'] = res_titles
            df['최저가'] = res_prices
            df['링크'] = res_links
            
            status_text.success("✅ 검색 완료! 결과를 확인하고 다운로드하세요.")
            st.dataframe(df)
            
            # 엑셀 다운로드
            def convert_df(df):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                return output.getvalue()

            csv = convert_df(df)

            st.download_button(
                label="📥 검색 결과 엑셀 다운로드",
                data=csv,
                file_name='최저가_검색결과.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )

    except Exception as e:

        st.error(f"오류가 발생했습니다: {e}")
