import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone, timedelta
import time

# --- [UI 디자인] 와이드 레이아웃 설정 ---
st.set_page_config(
    page_title="시장 최저가 & 자사 비교 분석", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- [보안] API 인증 정보 가져오기 ---
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID", "")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET", "")

def get_naver_shopping(query):
    if not CLIENT_ID or not CLIENT_SECRET:
        return []
    
    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": 50, 
        "sort": "sim"  
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get('items', [])
        else:
            return []
    except Exception as e:
        return []

# --- 메인 헤더 ---
st.title("🔍 가전 시장 최저가 & 자사 가격 비교 분석")
st.markdown("---")

# [핵심] 두 가지 모드로 탭 분리
tab_single, tab_batch = st.tabs(["🔎 단일 모델 상세 분석", "📊 엑셀 일괄 가격 비교 (Comparison)"])

# ==========================================
# 탭 1: 기존 단일 모델 상세 분석
# ==========================================
with tab_single:
    search_query = st.text_input("분석할 가전 모델명 또는 키워드를 입력하세요", placeholder="예: 에스프레소 머신")

    if search_query:
        with st.spinner("데이터를 분석 중입니다..."):
            items = get_naver_shopping(search_query)
            
            if items:
                parsed_data = []
                for item in items:
                    clean_title = item['title'].replace('<b>', '').replace('</b>', '')
                    try:
                        price = int(item['lprice'])
                    except:
                        price = 0
                        
                    parsed_data.append({
                        "이미지": item['image'],
                        "상품명": clean_title,
                        "최저가(원)": price,
                        "브랜드": item.get('brand', '기타') if item.get('brand') else '기타',
                        "쇼핑몰": item['mallName'] if item['mallName'] else '오픈마켓',
                        "링크": item['link']
                    })
                
                df = pd.DataFrame(parsed_data)
                df = df[df["최저가(원)"] > 0]
                df = df.sort_values(by="최저가(원)", ascending=True).reset_index(drop=True)
                
                if not df.empty:
                    st.sidebar.header("🎯 시장 데이터 필터링")
                    
                    min_p = int(df["최저가(원)"].min())
                    max_p = int(df["최저가(원)"].max())
                    if min_p < max_p:
                        price_range = st.sidebar.slider("가격대 범위 설정 (원)", min_value=min_p, max_value=max_p, value=(min_p, max_p), step=1000)
                    else:
                        price_range = (min_p, max_p)
                    
                    selected_malls = st.sidebar.multiselect("유통 채널 선택", options=sorted(list(df["쇼핑몰"].unique())), default=sorted(list(df["쇼핑몰"].unique())))
                    
                    filtered_df = df[
                        (df["최저가(원)"] >= price_range[0]) &
                        (df["최저가(원)"] <= price_range[1]) &
                        (df["쇼핑몰"].isin(selected_malls))
                    ].reset_index(drop=True)
                    
                    if not filtered_df.empty:
                        kst = timezone(timedelta(hours=9))
                        current_time = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M:%S")
                        st.caption(f"⏱️ 데이터 갱신 일시: {current_time} (KST)")
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("시장 최저가", f"{int(filtered_df['최저가(원)'].min()):,} 원")
                        m2.metric("평균 시장가", f"{int(filtered_df['최저가(원)'].mean()):,} 원")
                        m3.metric("분석 상품 수", f"{len(filtered_df)} 개")
                        
                        st.dataframe(
                            filtered_df,
                            column_config={
                                "이미지": st.column_config.ImageColumn("제품 이미지", width="small"),
                                "최저가(원)": st.column_config.ProgressColumn("최저가(원)", format="%d 원", min_value=0, max_value=int(filtered_df['최저가(원)'].max())),
                                "링크": st.column_config.LinkColumn("바로가기", display_text="이동")
                            },
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.warning("⚠️ 조건에 부합하는 데이터가 없습니다.")

# ==========================================
# 탭 2: 엑셀 파일 일괄 비교 모드 (신규 기능)
# ==========================================
with tab_batch:
    st.subheader("📁 자사 판매가 vs 온라인 최저가 일괄 비교")
    st.markdown("`모델명`, `자사판매가` 컬럼이 포함된 엑셀(.xlsx) 파일을 업로드하세요.")
    
    uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        try:
            # 엑셀 파일 읽기
            input_df = pd.read_excel(uploaded_file)
            
            # 필수 컬럼 확인
            if "모델명" not in input_df.columns or "자사판매가" not in input_df.columns:
                st.error("⚠️ 엑셀 파일 첫 번째 줄에 '모델명'과 '자사판매가' 컬럼이 반드시 있어야 합니다.")
            else:
                st.info(f"총 {len(input_df)}개의 모델 데이터를 확인했습니다. 실시간 최저가 조회를 시작합니다.")
                
                # 진행 상태 표시 바
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                results = []
                
                # 각 모델별로 API 호출하여 최저가 찾기
                for index, row in input_df.iterrows():
                    model_name = str(row['모델명'])
                    my_price = int(row['자사판매가'])
                    note = row.get('비고', '')
                    
                    status_text.text(f"🔍 '{model_name}' 실시간 가격 조회 중... ({index + 1}/{len(input_df)})")
                    
                    items = get_naver_shopping(model_name)
                    online_lowest = None
                    
                    if items:
                        prices = [int(item['lprice']) for item in items if item['lprice'].isdigit() and int(item['lprice']) > 0]
                        if prices:
                            online_lowest = min(prices)
                    
                    # 가격 차이 및 경쟁력 계산
                    if online_lowest:
                        diff = my_price - online_lowest
                        status = "✅ 우위" if diff <= 0 else "경고"
                    else:
                        diff = 0
                        status = "조회 불가"
                        online_lowest = 0
                    
                    results.append({
                        "모델명": model_name,
                        "비고": note,
                        "자사판매가(원)": my_price,
                        "온라인최저가(원)": online_lowest,
                        "가격차이(원)": diff,
                        "경쟁력": status
                    })
                    
                    # 진행률 업데이트 및 네이버 API 제한 방지용 짧은 대기
                    progress_bar.progress((index + 1) / len(input_df))
                    time.sleep(0.1) 
                
                status_text.text("✨ 데이터 분석이 완료되었습니다!")
                
                # 결과 데이터프레임 생성
                result_df = pd.DataFrame(results)
                
                # 가격 비교 시각화 (막대 그래프)
                st.markdown("### 📊 가격 경쟁력 시각화")
                
                # 그래프를 그리기 위해 데이터를 긴 형태(Melt)로 변환
                chart_df = result_df.melt(id_vars=['모델명'], value_vars=['자사판매가(원)', '온라인최저가(원)'], 
                                          var_name='분류', value_name='가격')
                
                # 0원(조회 불가)인 데이터는 그래프에서 제외
                chart_df = chart_df[chart_df['가격'] > 0]
                
                fig = px.bar(chart_df, x='모델명', y='가격', color='분류', barmode='group',
                             title="모델별 자사 판매가 vs 온라인 최저가 비교",
                             template="plotly_white",
                             color_discrete_map={"자사판매가(원)": "#3A6073", "온라인최저가(원)": "#E67E22"})
                st.plotly_chart(fig, use_container_width=True)
                
                # 최종 데이터 표 출력
                st.markdown("### 📋 상세 비교 리스트")
                
                csv_data = result_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 비교 결과 엑셀(CSV) 다운로드", data=csv_data, file_name="price_comparison_result.csv", mime="text/csv")
                
                # 표 서식 지정 (가격차이가 음수면 우위, 양수면 열위)
                def color_competitiveness(val):
                    color = 'green' if val == '✅ 우위' else 'red' if val == '경고' else 'grey'
                    return f'color: {color}; font-weight: bold'
                
                styled_df = result_df.style.map(color_competitiveness, subset=['경쟁력']).format({
                    "자사판매가(원)": "{:,}",
                    "온라인최저가(원)": "{:,}",
                    "가격차이(원)": "{:,}"
                })
                
                st.dataframe(styled_df, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"⚠️ 엑셀 파일을 읽는 중 오류가 발생했습니다. 양식을 다시 확인해 주세요. (에러: {e})")
