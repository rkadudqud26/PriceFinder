import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO

# ==========================================
# [1] 페이지 설정
# ==========================================
st.set_page_config(
    page_title="서주사이언티픽 최저가 검색 시스템 (Pro)",
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

import re # 정규표현식 라이브러리 추가 (맨 위에 있어야 함)

# ... (상단 로그인 및 설정 코드는 그대로 유지) ...

# ==========================================
# [3] 핵심 검색 로직 (노이즈 필터링 강화)
# ==========================================
CLIENT_ID = "SWML8CniVRJyDPKSeIkt"     # 본인 키 확인
CLIENT_SECRET = "C_U15jOct2"           # 본인 키 확인

# 🚫 검색에 방해되는 단어 리스트 (제조사 등에 포함되면 삭제)
NOISE_WORDS = ["시중품", "자체제작", "기타", "없음", "상세기재", "협력사", "대신무역", "도매상닷컴", "주식회사", "(주)"]

def clean_text(text):
    """특수문자 제거 및 노이즈 단어 삭제"""
    if pd.isna(text): return ""
    text = str(text)
    
    # 1. 특수문자(/, _, [], (), +)를 공백으로 치환
    text = re.sub(r"[/_\[\]\(\)\+\-\*]", " ", text)
    
    # 2. 노이즈 단어 제거
    for noise in NOISE_WORDS:
        text = text.replace(noise, "")
        
    return text.strip()

def extract_model_code_from_name(text):
    """상품명 등에서 '영어+숫자' 조합(모델명 패턴)만 쏙 뽑아냄"""
    # 예: "포스트잇 N686F-2" -> "N686F-2"
    match = re.search(r'[A-Za-z]+[-]?\d+|[A-Za-z]{2,}', str(text))
    if match:
        return match.group()
    return ""

def search_naver_api(query):
    """API 호출 (기존과 동일)"""
    # 쿼리가 너무 짧으면(1글자 이하) 실행 안 함
    if len(query.strip()) < 2: return {'found': False}

    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
    params = {"query": query, "display": 1, "sort": "asc"}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            items = response.json().get('items')
            if items:
                title = items[0]['title'].replace('<b>', '').replace('</b>', '')
                return {
                    'title': title,
                    'price': int(items[0]['lprice']),
                    'link': items[0]['link'],
                    'found': True
                }
    except:
        pass
    return {'found': False}

def smart_search_logic(row, cols_map):
    # 1. 데이터 가져오기 및 클리닝
    raw_name = str(row[cols_map['name']])
    raw_spec = str(row[cols_map['spec']]) if not pd.isna(row[cols_map['spec']]) else ""
    
    name = clean_text(raw_name)
    spec = clean_text(raw_spec)
    maker = clean_text(str(row[cols_map['maker']])) if cols_map['maker'] != "없음" else ""
    model = clean_text(str(row[cols_map['model']])) if cols_map['model'] != "없음" else ""

    # 상품명에서 모델명스러운 것 추출 (예: N686F-2)
    extracted_model = extract_model_code_from_name(raw_name)

    # 2. 검색 시나리오 (우선순위 재조정)
    queries = []
    
    # [전략 1] 제조사 + 모델명 (가장 깔끔함)
    if maker and model:
        queries.append(f"{maker} {model}")
    
    # [전략 2] 모델명 단독 (제조사가 '시중품'이라 지워졌을 때 유용)
    if model:
        queries.append(model)
        
    # [전략 3] 추출된 모델명 (상품명에 숨어있던 모델명)
    if extracted_model and extracted_model != model:
        queries.append(extracted_model)
        if maker:
            queries.append(f"{maker} {extracted_model}")

    # [전략 4] 제조사 + 상품명 (규격 제외) -> 규격에 잡다한 말이 많아서 제외하는 게 나을 때가 많음
    if maker:
        queries.append(f"{maker} {name}")
    
    # [전략 5] 상품명 + 규격 (최후의 수단)
    queries.append(f"{name} {spec}")
    
    # 3. 순차 실행
    for q in queries:
        q = q.strip()
        # 검색어가 너무 길면 오히려 방해되므로 앞 4단어만 자를 수도 있음 (선택)
        result = search_naver_api(q)
        if result['found']:
            result['used_keyword'] = q
            return result
            
    return {'title': "검색실패", 'price': 0, 'link': "", 'found': False, 'used_keyword': "실패"}

# ... (이하 UI 코드는 기존과 동일하게 유지) ...

# ==========================================
# [4] 메인 UI
# ==========================================
st.title("🚀 스마트 다중 검색 시스템")
st.markdown("""
**실패율을 줄이는 '3단계 검색'이 적용되었습니다.**
1. `제조사 + 모델명`으로 먼저 찾아봅니다. (가장 정확)
2. 안 나오면 `제조사 + 상품명 + 규격`으로 찾습니다.
3. 그래도 안 나오면 `상품명 + 규격`으로 찾습니다.
""")
st.divider()

uploaded_file = st.file_uploader("엑셀 파일 업로드", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    st.write("📂 **데이터 로드 완료**")
    st.dataframe(df.head(3))
    
    # 컬럼 매핑 (사용자가 지정)
    st.info("👇 정확한 검색을 위해 컬럼을 연결해주세요.")
    cols = list(df.columns)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        name_col = st.selectbox("상품명 (필수)", cols, index=0)
    with c2:
        spec_col = st.selectbox("규격 (필수)", cols, index=1 if len(cols)>1 else 0)
    with c3:
        # 제조사 자동 찾기 시도
        m_idx = next((i for i, c in enumerate(cols) if "제조" in str(c) or "브랜드" in str(c)), 0)
        maker_col = st.selectbox("제조사 (선택)", ["없음"] + cols, index=m_idx + 1)
    with c4:
        # 모델명 자동 찾기 시도
        mo_idx = next((i for i, c in enumerate(cols) if "모델" in str(c) or "Cat" in str(c)), 0)
        model_col = st.selectbox("모델명 (선택)", ["없음"] + cols, index=mo_idx + 1)
        
    cols_map = {
        'name': name_col, 'spec': spec_col, 
        'maker': maker_col if maker_col != "없음" else "없음",
        'model': model_col if model_col != "없음" else "없음"
    }

    if st.button("🔍 강화된 검색 시작", type="primary"):
        
        results_list = []
        progress_bar = st.progress(0)
        status_txt = st.empty()
        total = len(df)
        
        for i, row in df.iterrows():
            # 스마트 검색 실행
            res = smart_search_logic(row, cols_map)
            
            # 진행상황 표시
            status_txt.text(f"[{i+1}/{total}] 검색중... {res.get('used_keyword', '')}")
            
            # 결과 기록
            df.at[i, '네이버상품명'] = res['title']
            df.at[i, '최저가'] = res['price']
            df.at[i, '링크'] = res['link']
            df.at[i, '성공키워드'] = res.get('used_keyword', '')
            
            progress_bar.progress((i + 1) / total)
            time.sleep(0.15) # API 호출 제한 고려 (너무 빠르면 차단됨)
            
        status_txt.success("✅ 검색이 모두 완료되었습니다!")
        st.dataframe(df)
        
        # 다운로드
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            
        st.download_button(
            "📥 결과 엑셀 다운로드",
            data=output.getvalue(),
            file_name="스마트검색결과.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

