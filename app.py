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
# [4] 메인 UI (디버깅 강화 버전)
# ==========================================
st.title("🛒 스마트 다중 검색 시스템 (낚시제거)")
st.markdown("""
**10원짜리 미끼 상품을 걸러냅니다.**
설정한 **최소 금액**보다 싼 제품은 검색 결과에서 자동으로 제외하고, 그 다음 최저가를 찾아옵니다.
""")
st.divider()

uploaded_file = st.file_uploader("엑셀 파일 업로드", type=['xlsx'])

if uploaded_file:
    # 1. 파일 읽기 시도
    try:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
        st.write(f"📂 **데이터 로드 완료: {len(df)}개 행**")
    except Exception as e:
        st.error(f"❌ 엑셀 파일을 읽는 중 에러가 났습니다: {e}")
        st.stop()
    
    # 2. 가격 필터 설정
    with st.container():
        st.subheader("💰 가격 필터 설정")
        c_min, c_max = st.columns(2)
        with c_min:
            min_val = st.number_input("최소 가격 (원)", min_value=0, value=1000, step=100)
        with c_max:
            max_val = st.number_input("최대 가격 (원)", min_value=0, value=0, step=1000)
            
    st.divider()
    
    # 3. 컬럼 매핑
    st.info("👇 컬럼 연결")
    cols = list(df.columns)
    
    # 컬럼이 하나도 없으면 경고
    if len(cols) == 0:
        st.error("엑셀 파일에 데이터가 없거나 컬럼을 읽지 못했습니다.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    with c1: name_col = st.selectbox("상품명", cols, index=0)
    with c2: spec_col = st.selectbox("규격", cols, index=1 if len(cols)>1 else 0)
    with c3: maker_col = st.selectbox("제조사 (선택)", ["없음"] + cols, index=0)
    with c4: model_col = st.selectbox("모델명 (선택)", ["없음"] + cols, index=0)
        
    cols_map = {'name': name_col, 'spec': spec_col, 
                'maker': maker_col if maker_col != "없음" else "없음",
                'model': model_col if model_col != "없음" else "없음"}

    # 4. 검색 버튼 (디버깅 로그 추가)
    if st.button("🔍 검색 시작 (가격필터 적용)", type="primary"):
        st.write("🔄 시스템: 검색 로직을 시작합니다... (이 메시지가 보이면 버튼은 작동한 것입니다)")
        
        try:
            # 결과 담을 빈 컬럼 미리 생성 (필수!)
            df['네이버상품명'] = ""
            df['최저가'] = 0
            df['링크'] = ""
            df['성공키워드'] = ""
            
            results_list = []
            progress_bar = st.progress(0)
            status_txt = st.empty()
            total = len(df)
            
            for i, row in df.iterrows():
                # 검색 로직 실행
                res = smart_search_logic(row, cols_map, min_val, max_val)
                
                # 상태 메시지 업데이트
                status_txt.text(f"[{i+1}/{total}] 진행중... {res.get('used_keyword', '...')}")
                
                # 데이터프레임에 값 넣기 (안전한 방식인 loc 사용)
                df.loc[i, '네이버상품명'] = str(res['title'])
                df.loc[i, '최저가'] = int(res['price'])
                df.loc[i, '링크'] = str(res['link'])
                df.loc[i, '성공키워드'] = str(res.get('used_keyword', ''))
                
                progress_bar.progress((i + 1) / total)
                time.sleep(0.1) 
                
            status_txt.success("✅ 검색 완료!")
            st.dataframe(df)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
                
            st.download_button("📥 결과 다운로드", output.getvalue(), "스마트검색_가격필터.xlsx")
            
        except Exception as e:
            # 🚨 에러 발생 시 여기서 상세 내용을 화면에 뿌려줍니다.
            import traceback
            st.error("⛔ 프로그램 실행 중 오류가 발생했습니다.")
            st.code(traceback.format_exc()) # 에러의 상세 위치를 보여줌

