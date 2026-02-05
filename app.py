import streamlit as st
import pandas as pd
import requests
import time
import re
from io import BytesIO

# ==========================================
# [1] 페이지 설정
# ==========================================
st.set_page_config(
    page_title="서주사이언티픽 최저가 검색 시스템 (Pro+)",
    page_icon="🧬",
    layout="wide"
)

# ==========================================
# [2] 보안 기능
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🧬 서주사이언티픽 최저가 검색 시스템")
        password = st.text_input("접속 코드를 입력하세요", type="password")
        if st.button("접속"):
            if password == st.secrets["access_code"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("⛔ 승인되지 않은 코드입니다.")
    return False

if not check_password():
    st.stop()

# ==========================================
# [3] 핵심 로직 (가격 필터링 추가됨)
# ==========================================
CLIENT_ID = "SWML8CniVRJyDPKSeIkt"     # 본인 키 확인
CLIENT_SECRET = "C_U15jOct2"           # 본인 키 확인

# 🚫 노이즈 단어 리스트
NOISE_WORDS = ["시중품", "자체제작", "기타", "없음", "상세기재", "협력사", "대신무역", "도매상닷컴", "주식회사", "(주)"]

def clean_text(text):
    if pd.isna(text): return ""
    text = str(text)
    text = re.sub(r"[/_\[\]\(\)\+\-\*]", " ", text)
    for noise in NOISE_WORDS:
        text = text.replace(noise, "")
    return text.strip()

def extract_model_code_from_name(text):
    match = re.search(r'[A-Za-z]+[-]?\d+|[A-Za-z]{2,}', str(text))
    if match: return match.group()
    return ""

def search_naver_api(query, min_price, max_price):
    """
    API로 30개를 가져온 뒤, 가격 범위에 맞는 첫 번째 상품을 반환
    """
    if len(query.strip()) < 2: return {'found': False}

    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
    
    # 낚시 매물을 피하기 위해 상위 30개를 가져와서 검사합니다.
    params = {"query": query, "display": 30, "sort": "asc"} 
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            items = response.json().get('items')
            if items:
                # [중요] 가져온 30개 중에서 가격 조건에 맞는 놈 찾기
                for item in items:
                    lprice = int(item['lprice'])
                    
                    # 1. 최소 금액보다 작으면 패스 (낚시 매물)
                    if lprice < min_price:
                        continue
                    
                    # 2. 최대 금액보다 크면 패스 (너무 비싼 것)
                    if max_price > 0 and lprice > max_price:
                        continue
                        
                    # 조건을 통과하면 이 상품을 선택!
                    title = item['title'].replace('<b>', '').replace('</b>', '')
                    return {
                        'title': title,
                        'price': lprice,
                        'link': item['link'],
                        'found': True
                    }
    except:
        pass
    return {'found': False}

def smart_search_logic(row, cols_map, min_p, max_p):
    raw_name = str(row[cols_map['name']])
    raw_spec = str(row[cols_map['spec']]) if not pd.isna(row[cols_map['spec']]) else ""
    
    name = clean_text(raw_name)
    spec = clean_text(raw_spec)
    maker = clean_text(str(row[cols_map['maker']])) if cols_map['maker'] != "없음" else ""
    model = clean_text(str(row[cols_map['model']])) if cols_map['model'] != "없음" else ""
    extracted_model = extract_model_code_from_name(raw_name)

    queries = []
    
    if maker and model: queries.append(f"{maker} {model}")
    if model: queries.append(model)
    if extracted_model and extracted_model != model:
        queries.append(extracted_model)
        if maker: queries.append(f"{maker} {extracted_model}")
    if maker: queries.append(f"{maker} {name}")
    queries.append(f"{name} {spec}")
    
    for q in queries:
        q = q.strip()
        result = search_naver_api(q, min_p, max_p) # 가격 범위 전달
        if result['found']:
            result['used_keyword'] = q
            return result
            
    return {'title': "검색실패(범위내없음)", 'price': 0, 'link': "", 'found': False, 'used_keyword': "실패"}

# ==========================================
# [4] 메인 UI
# ==========================================
st.title("🛒 스마트 다중 검색 시스템 (낚시제거)")
st.markdown("""
**10원짜리 미끼 상품을 걸러냅니다.**
설정한 **최소 금액**보다 싼 제품은 검색 결과에서 자동으로 제외하고, 그 다음 최저가를 찾아옵니다.
""")
st.divider()

uploaded_file = st.file_uploader("엑셀 파일 업로드", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    st.write("📂 **데이터 로드 완료**")
    
    # -----------------------------------------------------
    # 가격 필터 설정 (사이드바 혹은 메인 상단)
    # -----------------------------------------------------
    with st.container():
        st.subheader("💰 가격 필터 설정")
        c_min, c_max = st.columns(2)
        with c_min:
            min_val = st.number_input(
                "최소 가격 (원) - 이 가격 미만은 무시함", 
                min_value=0, value=1000, step=100, 
                help="10원, 100원짜리 낚시 매물을 피하려면 1000원 정도로 설정하세요."
            )
        with c_max:
            max_val = st.number_input(
                "최대 가격 (원) - 0이면 제한 없음", 
                min_value=0, value=0, step=1000,
                help="너무 비싼 장비가 검색되는걸 막고 싶으면 설정하세요."
            )
            
    st.divider()
    
    # 컬럼 매핑
    st.info("👇 컬럼 연결")
    cols = list(df.columns)
    c1, c2, c3, c4 = st.columns(4)
    with c1: name_col = st.selectbox("상품명", cols, index=0)
    with c2: spec_col = st.selectbox("규격", cols, index=1 if len(cols)>1 else 0)
    with c3: maker_col = st.selectbox("제조사 (선택)", ["없음"] + cols, index=next((i for i, c in enumerate(cols) if "제조" in str(c)), 0) + 1)
    with c4: model_col = st.selectbox("모델명 (선택)", ["없음"] + cols, index=next((i for i, c in enumerate(cols) if "모델" in str(c)), 0) + 1)
        
    cols_map = {'name': name_col, 'spec': spec_col, 
                'maker': maker_col if maker_col != "없음" else "없음",
                'model': model_col if model_col != "없음" else "없음"}

# [수정된 코드] 검색 버튼 로직
    if st.button("🔍 검색 시작 (가격필터 적용)", type="primary"):
        
        # [안전장치 1] 에러 발생 시 화면에 표시하기 위한 try-except
        try:
            results_list = []
            progress_bar = st.progress(0)
            status_txt = st.empty()
            total = len(df)
            
            # [⭐ 핵심 수정] 빈 컬럼을 미리 만들어야 에러가 안 납니다!
            df['네이버상품명'] = ""
            df['최저가'] = 0
            df['링크'] = ""
            df['성공키워드'] = ""
            
            for i, row in df.iterrows():
                # 사용자가 설정한 min_val, max_val을 넘겨줌
                res = smart_search_logic(row, cols_map, min_val, max_val)
                
                status_txt.text(f"[{i+1}/{total}] 검색중... {res.get('used_keyword', '')}")
                
                # 이제 컬럼이 존재하므로 df.at을 써도 안전합니다.
                df.at[i, '네이버상품명'] = res['title']
                df.at[i, '최저가'] = res['price']
                df.at[i, '링크'] = res['link']
                df.at[i, '성공키워드'] = res.get('used_keyword', '')
                
                progress_bar.progress((i + 1) / total)
                time.sleep(0.1) 
                
            status_txt.success("✅ 완료! 낚시 매물이 걸러졌는지 확인해보세요.")
            st.dataframe(df)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
                
            st.download_button("📥 결과 다운로드", output.getvalue(), "스마트검색_가격필터.xlsx")
        
        except Exception as e:
            # 에러가 나면 빨간 박스로 알려줌
            st.error(f"⛔ 오류가 발생했습니다: {e}")
