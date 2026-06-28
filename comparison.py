import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone, timedelta
import time
import io

# --- [UI 디자인] 와이드 레이아웃 설정 ---
st.set_page_config(
    page_title="시장 최저가 & 자사 비교 대시보드", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- [보안] API 인증 정보 가져오기 ---
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID", "")
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET", "")

# --- [설정] 검색 제외 키워드 ---
# 이 리스트에 포함된 단어가 상품명에 들어가 있으면 결과에서 완전히 제외합니다.
EXCLUDE_KEYWORDS = [
    "렌탈", "대여", "부속", "부품", "소모품", "필터", 
    "거치대", "액세서리", "악세사리", "케이스", "칼날", 
    "탬퍼", "세척액", "용기", "보상판매"
]

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
            raw_items = response.json().get('items', [])
            filtered_items = []
            
            for item in raw_items:
                # 네이버 API가 보내주는 <b> 태그 사전 제거
                clean_title = item['title'].replace('<b>', '').replace('</b>', '')
                
                # 제외 키워드가 하나라도 상품명에 포함되어 있는지 검사
                if not any(keyword in clean_title for keyword in EXCLUDE_KEYWORDS):
                    item['title'] = clean_title # 깔끔해진 제목으로 교체
                    filtered_items.append(item)
                    
            return filtered_items
        else:
            return []
    except Exception as e:
        return []

# --- 메인 헤더 ---
st.title("🔍 가전 시장 최저가 & 자사 가격 비교 대시보드")
st.markdown("---")

# [핵심] 세 가지 모드로 탭 분리
tab_single, tab_batch, tab_coupang = st.tabs([
    "🔎 단일 모델 상세 분석", 
    "📊 엑셀 일괄 비교 (전체 온라인)", 
    "🚀 엑셀 일괄 비교 (쿠팡 전용)"
])

# ==========================================
# 탭 1: 단일 모델 상세 분석
# ==========================================
with tab_single:
    search_query = st.text_input("분석할 가전 모델명 또는 키워드를 입력하세요", placeholder="예: 에스프레소 머신, 포터블믹서기")

    if search_query:
        with st.spinner("데이터를 분석 중입니다... (렌탈/부속품 제외 중)"):
            items = get_naver_shopping(search_query)
            
            if items:
                parsed_data = []
                for item in items:
                    try:
                        price = int(item['lprice'])
                    except:
                        price = 0
                        
                    parsed_data.append({
                        "이미지": item['image'],
                        "상품명": item['title'],
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
# 탭 2: 엑셀 파일 일괄 비교 모드 (전체 쇼핑몰)
# ==========================================
with tab_batch:
    st.subheader("📁 자사 판매가 vs 온라인 전체 최저가 일괄 비교")
    st.markdown("`모델명`, `자사판매가` 컬럼이 포함된 엑셀(.xlsx) 파일을 업로드하세요.")
    
    with st.expander("💡 엑셀 업로드 양식 예시 보기 및 템플릿 다운로드"):
        template_df = pd.DataFrame({
            "모델명": ["드롱기 아이코나 빈티지", "네스프레소 버츄오 팝", "닌자 포터블믹서기"],
            "자사판매가": [150000, 120000, 85000],
            "비고": ["에스프레소 머신", "홈카페 기획전", "파워모터 적용"]
        })
        st.dataframe(template_df, use_container_width=True, hide_index=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            template_df.to_excel(writer, index=False, sheet_name='Sheet1')
        st.download_button(label="📥 엑셀 양식 템플릿 다운로드 (.xlsx)", data=buffer.getvalue(), file_name="price_comparison_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    st.markdown("---")
    uploaded_file = st.file_uploader("전체 쇼핑몰 비교용 엑셀 파일을 업로드해 주세요", type=["xlsx", "xls"], key="upload_all")
    
    if uploaded_file is not None:
        try:
            input_df = pd.read_excel(uploaded_file)
            if "모델명" not in input_df.columns or "자사판매가" not in input_df.columns:
                st.error("⚠️ 엑셀 파일 첫 번째 줄에 '모델명'과 '자사판매가' 컬럼이 반드시 있어야 합니다.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                results = []
                
                for index, row in input_df.iterrows():
                    model_name = str(row['모델명'])
                    my_price = int(row['자사판매가']) if pd.notnull(row['자사판매가']) else 0
                    note = str(row['비고']) if '비고' in row and pd.notnull(row['비고']) else ''
                    
                    status_text.text(f"🔍 '{model_name}' 전체 쇼핑몰 최저가 조회 중... ({index + 1}/{len(input_df)})")
                    items = get_naver_shopping(model_name)
                    
                    online_lowest = 0
                    lowest_mall = "-"
                    status = "조회 불가"
                    diff = 0
                    
                    if items:
                        valid_items = [item for item in items if item['lprice'].isdigit() and int(item['lprice']) > 0]
                        if valid_items:
                            lowest_item = min(valid_items, key=lambda x: int(x['lprice']))
                            online_lowest = int(lowest_item['lprice'])
                            lowest_mall = lowest_item['mallName'] if lowest_item['mallName'] else "오픈마켓"
                            diff = my_price - online_lowest
                            status = "✅ 우위" if diff <= 0 else "경고"
                    
                    results.append({
                        "모델명": model_name, "비고": note, "자사판매가(원)": my_price,
                        "온라인최저가(원)": online_lowest, "최저가쇼핑몰": lowest_mall,
                        "가격차이(원)": diff, "경쟁력": status
                    })
                    
                    progress_bar.progress((index + 1) / len(input_df))
                    time.sleep(0.1) 
                
                status_text.text("✨ 데이터 분석이 완료되었습니다!")
                result_df = pd.DataFrame(results)
                
                st.markdown("### 📊 가격 경쟁력 시각화 (전체)")
                chart_df = result_df.melt(id_vars=['모델명'], value_vars=['자사판매가(원)', '온라인최저가(원)'], var_name='분류', value_name='가격')
                chart_df = chart_df[chart_df['가격'] > 0]
                fig = px.bar(chart_df, x='모델명', y='가격', color='분류', barmode='group', template="plotly_white", color_discrete_map={"자사판매가(원)": "#3A6073", "온라인최저가(원)": "#E67E22"})
                st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("### 📋 상세 비교 리스트")
                csv_data = result_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 전체 비교 결과 엑셀(CSV) 다운로드", data=csv_data, file_name="all_price_comparison.csv", mime="text/csv", key="down_all")
                
                def color_competitiveness(val):
                    color = 'green' if val == '✅ 우위' else 'red' if val == '경고' else 'grey'
                    return f'color: {color}; font-weight: bold'
                
                styled_df = result_df.style.map(color_competitiveness, subset=['경쟁력']).format({"자사판매가(원)": "{:,}", "온라인최저가(원)": "{:,}", "가격차이(원)": "{:,}"})
                st.dataframe(styled_df, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"⚠️ 오류가 발생했습니다: {e}")

# ==========================================
# 탭 3: 엑셀 파일 일괄 비교 모드 (쿠팡 전용)
# ==========================================
with tab_coupang:
    st.subheader("🚀 자사 판매가 vs 쿠팡 최저가 일괄 비교")
    st.markdown("네이버 쇼핑 데이터 중 **'쿠팡'** 채널에서 판매되는 최저가만 필터링하여 비교합니다. 양식은 이전 탭과 동일합니다.")
    
    uploaded_file_cp = st.file_uploader("쿠팡 비교용 엑셀 파일을 업로드해 주세요", type=["xlsx", "xls"], key="upload_cp")
    
    if uploaded_file_cp is not None:
        try:
            input_df_cp = pd.read_excel(uploaded_file_cp)
            if "모델명" not in input_df_cp.columns or "자사판매가" not in input_df_cp.columns:
                st.error("⚠️ 엑셀 파일 첫 번째 줄에 '모델명'과 '자사판매가' 컬럼이 반드시 있어야 합니다.")
            else:
                progress_bar_cp = st.progress(0)
                status_text_cp = st.empty()
                results_cp = []
                
                for index, row in input_df_cp.iterrows():
                    model_name = str(row['모델명'])
                    my_price = int(row['자사판매가']) if pd.notnull(row['자사판매가']) else 0
                    note = str(row['비고']) if '비고' in row and pd.notnull(row['비고']) else ''
                    
                    status_text_cp.text(f"🔍 '{model_name}' 쿠팡 최저가 필터링 중... ({index + 1}/{len(input_df_cp)})")
                    items = get_naver_shopping(model_name)
                    
                    coupang_lowest = 0
                    status = "쿠팡 판매 안함"
                    diff = 0
                    
                    if items:
                        valid_items = [item for item in items if item['lprice'].isdigit() and int(item['lprice']) > 0]
                        coupang_items = [item for item in valid_items if "쿠팡" in item['mallName']]
                        
                        if coupang_items:
                            lowest_item = min(coupang_items, key=lambda x: int(x['lprice']))
                            coupang_lowest = int(lowest_item['lprice'])
                            diff = my_price - coupang_lowest
                            status = "✅ 우위" if diff <= 0 else "경고"
                    
                    results_cp.append({
                        "모델명": model_name, 
                        "비고": note, 
                        "자사판매가(원)": my_price,
                        "쿠팡최저가(원)": coupang_lowest, 
                        "가격차이(원)": diff, 
                        "경쟁력": status
                    })
                    
                    progress_bar_cp.progress((index + 1) / len(input_df_cp))
                    time.sleep(0.1) 
                
                status_text_cp.text("✨ 쿠팡 전용 데이터 분석이 완료되었습니다!")
                result_df_cp = pd.DataFrame(results_cp)
                
                st.markdown("### 📊 쿠팡 가격 경쟁력 시각화")
                chart_df_cp = result_df_cp.melt(id_vars=['모델명'], value_vars=['자사판매가(원)', '쿠팡최저가(원)'], var_name='분류', value_name='가격')
                chart_df_cp = chart_df_cp[chart_df_cp['가격'] > 0] 
                
                fig_cp = px.bar(chart_df_cp, x='모델명', y='가격', color='분류', barmode='group', template="plotly_white", color_discrete_map={"자사판매가(원)": "#3A6073", "쿠팡최저가(원)": "#E74C3C"})
                st.plotly_chart(fig_cp, use_container_width=True)
                
                st.markdown("### 📋 쿠팡 상세 비교 리스트")
                csv_data_cp = result_df_cp.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 쿠팡 비교 결과 엑셀(CSV) 다운로드", data=csv_data_cp, file_name="coupang_price_comparison.csv", mime="text/csv", key="down_cp")
                
                def color_competitiveness_cp(val):
                    color = 'green' if val == '✅ 우위' else 'red' if val == '경고' else 'grey'
                    return f'color: {color}; font-weight: bold'
                
                styled_df_cp = result_df_cp.style.map(color_competitiveness_cp, subset=['경쟁력']).format({"자사판매가(원)": "{:,}", "쿠팡최저가(원)": "{:,}", "가격차이(원)": "{:,}"})
                st.dataframe(styled_df_cp, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"⚠️ 오류가 발생했습니다: {e}")
