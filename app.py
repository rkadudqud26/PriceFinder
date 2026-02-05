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
    page_title="서주 최저가 검색 (Fast)",
    page_icon="⚡",
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
        st.markdown("### ⚡ 서주 최저가 검색 (고속버전)")
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
# [3] 핵심 검색 로직 (군더더기 제거)
# ==========================================
CLIENT_ID = "SWML8CniVRJyDPKSeIkt"     # 본인 키 확인
CLIENT_SECRET = "C_U15jOct2"           # 본인 키 확인

# 검색 방해 단어 최소화
NOISE_WORDS = ["시중품", "자체제작", "기타", "없음", "상세기재", "협력사", "(주)", "주식회사"]

def clean_text(text):
    if pd.isna(text): return ""
    text = str(text)
    # 특수문자 제거하되, 모델명에 쓰이는 하이픈(-)은 살릴 수도 있음 (여기선 안전하게 공백 처리)
    text = re.sub(r"[/_\[\]\(\)\+\*]", " ", text)
    for noise in NOISE_WORDS:
        text = text.replace(noise, "")
    return text.strip()

def search_naver_api(query, min_price, max_price):
    """
    API 호출: 빠르고 간결하게
    """
    if len(query) < 2: return None

    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
    # 낚시 제거를 위해 20개까지만 봄 (30개는 너무 느림)
    params = {"query": query, "display": 20, "sort": "asc"} 
    
    try:
        # 타임아웃 2초 (빨리 포기하고 다음 거 찾는 게 나음)
        response = requests.get(url, headers=headers, params=params, timeout=2)
        
        if response.status_code == 200:
            items = response.json().get('items')
            if items:
                for item in items:
                    lprice = int(item['lprice'])
                    
                    # 가격 필터
                    if lprice < min_price: continue
                    if max_price > 0 and lprice > max_price: continue
                        
                    # 찾았다! (HTML 태그 제거)
                    title = item['title'].replace('<b>', '').replace('</b>', '')
                    return {
                        'title': title,
                        'price': lprice,
                        'link': item['link'],
                        'found': True
                    }
    except:
        pass
    return None

def smart_search_logic(row, cols_map, min_p, max_p):
    # 데이터 전처리
    raw_name = str(row[cols_map['name']])
    name = clean_text(raw_name)
    spec = clean_text(str(row[cols_map['spec']])) if not pd.isna(row[cols_map['spec']]) else ""
    maker = clean_text(str(row[cols_map['maker']])) if cols_map['maker'] != "없음" else ""
    model = clean_text(str(row[cols_map['model']])) if cols_map['model'] != "없음" else ""

    # [전략 수정] 가장 확률 높은 순서대로 딱 3번만 시도 (속도 향상)
    queries = []
    
    # 1순위: 제조사 + 모델명 (가장 정확)
    if maker and model: 
        queries.append(f"{maker} {model}")
    
    # 2순위: 모델명 단독 (모델명이 확실하다면 제조사 없어도 나옴)
    if model:
        queries.append(model)
        
    # 3순위: 제조사 + 상품명 (규격은 너무 길어서 오히려 방해될 때가 많음)
    if maker:
        queries.append(f"{maker} {name}")
    
    # 4순위: 상품명 + 규격 (최후의 수단)
    queries.append(f"{name} {spec}")
    
    # 순차 실행 (찾으면 바로 종료 -> 속도 향상)
    for q in queries:
        result = search_naver_api(q.strip(), min_p, max_p)
        if result:
            result['used_keyword'] = q
            return result
            
    return {'title': "검색실패", 'price': 0, 'link': "", 'found': False, 'used_keyword': ""}

# ==========================================
# [4] 메인 UI
# ==========================================
st.title("🛒 최저가 검색 (Fast & Smart)")
st.caption("속도와 정확도 위주로 최적화되었습니다.")

uploaded_file = st.file_uploader("엑셀 파일 업로드", type=['xlsx'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
        st.success(f"📂 데이터 {len(df)}개 로드 완료")
    except:
        st.error("엑셀 파일 읽기 실패")
        st.stop()

    # 가격 설정 (기본값을 100원으로 낮춤 -> 멍청함 방지)
    with st.expander("💰 가격 필터 설정 (필요시 변경)", expanded=True):
        c1, c2 = st.columns(2)
        with c1: 
            min_val = st.number_input("최소 가격 (원)", value=100, step=100, help="이 가격보다 싼 건 무시합니다.")
        with c2: 
            max_val = st.number_input("최대 가격 (원)", value=0, step=10000)

    # 컬럼 매핑
    cols = list(df.columns)
    c1, c2, c3, c4 = st.columns(4)
    with c1: name_col = st.selectbox("상품명", cols, index=0)
    with c2: spec_col = st.selectbox("규격", cols, index=1 if len(cols)>1 else 0)
    with c3: maker_col = st.selectbox("제조사 (선택)", ["없음"] + cols)
    with c4: model_col = st.selectbox("모델명 (선택)", ["없음"] + cols)
        
    cols_map = {'name': name_col, 'spec': spec_col, 
                'maker': maker_col, 'model': model_col}

    # 실행 버튼
    if st.button("🚀 빠른 검색 시작", type="primary"):
        
        # 결과 컬럼 생성
        df['네이버상품명'] = ""
        df['최저가'] = 0
        df['링크'] = ""
        df['성공키워드'] = ""
        
        # 진행바
        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(df)
        
        for i, row in df.iterrows():
            res = smart_search_logic(row, cols_map, min_val, max_val)
            
            # 값 입력 (loc 사용)
            df.loc[i, '네이버상품명'] = res['title']
            df.loc[i, '최저가'] = res['price']
            df.loc[i, '링크'] = res['link']
            df.loc[i, '성공키워드'] = res['used_keyword']
            
            # 진행바 업데이트 (텍스트 로그 최소화)
            progress_bar.progress((i + 1) / total)
            status_text.text(f"검색 중... {i+1}/{total}")
            
            # 딜레이 최소화 (0.05초)
            time.sleep(0.05)
            
        status_text.success("✅ 완료!")
        st.dataframe(df)
        
        # 다운로드
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 결과 다운로드", output.getvalue(), "빠른검색결과.xlsx")
