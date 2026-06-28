import streamlit as st
import requests
import pandas as pd

# --- API 설정 ---
# 네이버 개발자 센터에서 발급받은 ID와 Secret을 입력해야 작동합니다.
CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]

def get_naver_shopping(query):
    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": 10, # 가져올 상품 개수 (최대 100개)
        "sort": "sim"  # 정렬 방식 (sim: 정확도순, asc: 가격오름차순)
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()['items']
    else:
        st.error(f"Error: {response.status_code}")
        return []

# --- 대시보드 UI ---
st.title("🛒 실시간 네이버 최저가 대시보드")
st.markdown("---")

search_query = st.text_input("검색할 가전 모델명이나 키워드를 입력하세요", placeholder="예: 에스프레소 머신")

if st.button("검색") and search_query:
    with st.spinner("네이버 쇼핑에서 데이터를 가져오는 중..."):
        items = get_naver_shopping(search_query)
        
        if items:
            # 가져온 데이터를 표로 만들기 위해 가공
            parsed_data = []
            for item in items:
                # 네이버가 보내주는 데이터에는 <b> 태그가 섞여 있어 제거가 필요함
                clean_title = item['title'].replace('<b>', '').replace('</b>', '')
                parsed_data.append({
                    "상품명": clean_title,
                    "최저가(원)": int(item['lprice']),
                    "쇼핑몰": item['mallName'],
                    "링크": item['link']
                })
                
            df = pd.DataFrame(parsed_data)
            
            # 가격 기준으로 예쁘게 콤마(,) 포맷팅 적용
            df['최저가(원)'] = df['최저가(원)'].apply(lambda x: f"{x:,}")
            
            st.success(f"'{search_query}' 검색 결과입니다.")
            st.dataframe(df, use_container_width=True)