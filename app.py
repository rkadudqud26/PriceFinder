import streamlit as st
import pandas as pd
import requests
import time
import re
from io import BytesIO
import traceback # 에러 위치 추적용

# ==========================================
# [1] 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="서주 최저가 검색 (디버깅모드)",
    page_icon="🐞",
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
        st.markdown("### 🐞 서주 최저가 검색 (디버깅모드)")
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
# [3] 핵심 로직 (타임아웃 및 로그 추가)
# ==========================================
CLIENT_ID = "SWML8CniVRJyDPKSeIkt"     
CLIENT_SECRET = "C_U15jOct2"           

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

def search_naver_api(query, min_price, max_price, log_area):
    """
    API 호출 함수 (타임아웃 + 디버깅 로그 추가)
    """
    if len(query.strip()) < 2: return {'found': False}

    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
    params = {"query": query, "display": 30, "sort": "asc"} 
    
    try:
        # [중요] timeout=3 설정: 3초 안에 응답 없으면 에러 발생시키고 넘어감 (무한대기 방지)
        response = requests.get(url, headers=headers, params=params, timeout=3)
        
        if response.status_code == 200:
            items = response.json().get('items')
            if items:
                for item in items:
                    lprice = int(item['lprice'])
                    if lprice < min_price: continue
                    if max_price > 0 and lprice > max_price: continue
                        
                    title = item['title'].replace('<b>', '').replace('</b>', '')
                    return {
                        'title': title,
                        'price': lprice,
                        'link': item['link'],
                        'found': True
                    }
        else:
            # 200 OK가 아니면 에러 코드 출력
            log_area.text(f"⚠️ API 오류: {response.status_code} (키 확인 필요)")
            
    except requests.exceptions.Timeout:
        log_area.text(f"⏰ 타임아웃: '{query}' 검색 중 네이버가 응답하지 않음")
    except Exception as e:
        log_area.text(f"💥 통신 에러: {e}")
        
    return {'found': False}

def smart_search_logic(row, cols_map, min_p, max_p, log_area):
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
    queries.append(f"{name} {spec}")
    
    for q in queries:
        q = q.strip()
        result = search_naver_api(q, min_p, max_p, log_area)
        if result['found']:
            result['used_keyword'] = q
            return result
            
    return {'title': "검색실패", 'price': 0, 'link': "", 'found': False, 'used_keyword': "실패"}

# ==========================================
# [4] 메인 UI
# ==========================================
st.title("🐞 검색 시스템 (디버깅 모드)")
st.info("실행이 멈추는지 확인하기 위해 진행 상황을 실시간으로 표시합니다.")

uploaded_file = st.file_uploader("엑셀 파일 업로드", type=['xlsx'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
        st.write(f"📂 데이터 로드 완료: {len(df)}행")
    except Exception as e:
        st.error(f"파일 읽기 실패: {e}")
        st.stop()

    with st.container():
        c1, c2 = st.columns(2)
        with c1: min_val = st.number_input("최소 가격", value=1000, step=100)
        with c2: max_val = st.number_input("최대 가격", value=0, step=1000)

    cols = list(df.columns)
    c1, c2, c3, c4 = st.columns(4)
    with c1: name_col = st.selectbox("상품명", cols, index=0)
    with c2: spec_col = st.selectbox("규격", cols, index=1 if len(cols)>1 else 0)
    with c3: maker_col = st.selectbox("제조사", ["없음"] + cols)
    with c4: model_col = st.selectbox("모델명", ["없음"] + cols)
        
    cols_map = {'name': name_col, 'spec': spec_col, 
                'maker': maker_col if maker_col != "없음" else "없음",
                'model': model_col if model_col != "없음" else "없음"}

    # =========================================================
    # [수정됨] 실행 로그를 보여주는 공간 (Expander)
    # =========================================================
    log_expander = st.expander("📝 실시간 실행 로그 (클릭해서 열어보세요)", expanded=True)
    log_area = log_expander.empty()
    
    if st.button("🔍 검색 시작 (Click)", type="primary"):
        st.write("🚀 시스템: 검색 시작 버튼이 눌렸습니다.")
        
        try:
            # 1. 컬럼 생성
            df['네이버상품명'] = ""
            df['최저가'] = 0
            df['링크'] = ""
            df['성공키워드'] = ""
            
            st.write("✅ 시스템: 결과 저장용 컬럼 생성 완료. 반복문 진입합니다.")
            
            progress_bar = st.progress(0)
            status_txt = st.empty()
            total = len(df)
            
            for i, row in df.iterrows():
                # 로그 출력
                log_area.text(f"▶ [{i+1}/{total}] '{row[name_col]}' 검색 시도 중...")
                
                # 검색 실행 (timeout 적용됨)
                res = smart_search_logic(row, cols_map, min_val, max_val, log_area)
                
                # 결과 기록
                df.loc[i, '네이버상품명'] = str(res['title'])
                df.loc[i, '최저가'] = int(res['price'])
                df.loc[i, '링크'] = str(res['link'])
                df.loc[i, '성공키워드'] = str(res.get('used_keyword', ''))
                
                # 진행률 업데이트
                progress_bar.progress((i + 1) / total)
                status_txt.text(f"✅ [{i+1}/{total}] 완료 (가격: {res['price']}원)")
                
                # [중요] 너무 빠르면 차단되므로 0.2초 대기
                time.sleep(0.2)
                
            st.success("🎉 모든 검색이 완료되었습니다!")
            st.dataframe(df)
            
            # 다운로드 버튼
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 결과 엑셀 다운로드", output.getvalue(), "검색결과.xlsx")
            
        except Exception as e:
            st.error("⛔ 치명적인 오류 발생!")
            st.error(f"에러 내용: {e}")
            # 에러 위치 상세 출력
            st.code(traceback.format_exc())
