import streamlit as st
import io
from PIL import Image, ImageDraw
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import tempfile
import os
import plotly.graph_objects as go
import plotly.express as px

# 페이지 설정
st.set_page_config(
    page_title="PDF 전자서명 추가",
    page_icon="✍️",
    layout="wide"
)

st.title("✍️ PDF 전자서명 추가 도구")
st.markdown("---")

# 세션 상태 초기화
if 'pdf_images' not in st.session_state:
    st.session_state.pdf_images = None
if 'pdf_document' not in st.session_state:
    st.session_state.pdf_document = None
if 'signature_image' not in st.session_state:
    st.session_state.signature_image = None
if 'signature_positions' not in st.session_state:
    st.session_state.signature_positions = {}
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0

@st.cache_data
def convert_pdf_to_images(pdf_bytes):
    """PDF를 이미지로 변환 (PyMuPDF 사용)"""
    try:
        # PDF 문서 열기
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        
        # 각 페이지를 이미지로 변환
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            # 고해상도로 렌더링 (matrix로 스케일 조정)
            mat = fitz.Matrix(2.0, 2.0)  # 2배 확대
            pix = page.get_pixmap(matrix=mat)
            
            # PIL Image로 변환
            img_data = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
        
        pdf_document.close()
        return images, len(images)
        
    except Exception as e:
        st.error(f"PDF 변환 중 오류가 발생했습니다: {str(e)}")
        return None, 0

def resize_signature(signature_img, max_width=200, max_height=100):
    """서명 이미지 크기 조정"""
    # 비율 유지하며 크기 조정
    ratio = min(max_width / signature_img.width, max_height / signature_img.height)
    new_size = (int(signature_img.width * ratio), int(signature_img.height * ratio))
    return signature_img.resize(new_size, Image.Resampling.LANCZOS)

def add_signature_to_image(base_image, signature_img, position, signature_size=(150, 75)):
    """이미지에 서명 추가"""
    # 이미지 복사
    result_image = base_image.copy()
    
    # 서명 이미지 크기 조정
    signature_resized = signature_img.resize(signature_size, Image.Resampling.LANCZOS)
    
    # 투명도 처리를 위해 RGBA 모드로 변환
    if signature_resized.mode != 'RGBA':
        signature_resized = signature_resized.convert('RGBA')
    
    if result_image.mode != 'RGBA':
        result_image = result_image.convert('RGBA')
    
    # 서명 합성
    result_image.paste(signature_resized, position, signature_resized)
    
    return result_image.convert('RGB')

def create_pdf_with_signature_pymupdf(pdf_bytes, signature_positions, signature_img):
    """PyMuPDF를 사용해 서명이 추가된 PDF 생성"""
    try:
        # 원본 PDF 열기
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # 서명 이미지를 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_sig:
            signature_img.save(tmp_sig.name, format='PNG')
            sig_path = tmp_sig.name
        
        # 각 페이지에 서명 추가
        for page_num in signature_positions:
            if page_num < len(pdf_document):
                page = pdf_document.load_page(page_num)
                
                # 좌표 변환 (이미지 좌표 -> PDF 좌표)
                x, y = signature_positions[page_num]
                
                # 페이지 크기 가져오기
                page_rect = page.rect
                
                # 이미지 좌표를 PDF 좌표로 변환
                # (이미지는 2배 확대되어 있으므로 좌표를 반으로 나눔)
                pdf_x = x / 2
                pdf_y = y / 2
                
                # 서명 크기 설정 (PDF 좌표계에서)
                sig_width = 150 / 2  # 75 포인트
                sig_height = 75 / 2  # 37.5 포인트
                
                # 서명 이미지 삽입
                sig_rect = fitz.Rect(pdf_x, pdf_y, pdf_x + sig_width, pdf_y + sig_height)
                page.insert_image(sig_rect, filename=sig_path)
        
        # PDF를 바이트로 저장
        pdf_bytes_result = pdf_document.tobytes()
        pdf_document.close()
        
        # 임시 파일 삭제
        os.unlink(sig_path)
        
        return io.BytesIO(pdf_bytes_result)
        
    except Exception as e:
        st.error(f"PDF 생성 중 오류가 발생했습니다: {str(e)}")
        return None

# 사이드바
with st.sidebar:
    st.header("📁 파일 업로드")
    
    # PDF 파일 업로드
    pdf_file = st.file_uploader(
        "PDF 파일을 선택하세요",
        type=['pdf'],
        help="서명을 추가할 PDF 파일을 업로드하세요"
    )
    
    # 서명 이미지 업로드
    signature_file = st.file_uploader(
        "전자서명 이미지를 선택하세요",
        type=['png', 'jpg', 'jpeg'],
        help="투명 배경의 PNG 파일을 권장합니다"
    )
    
    if signature_file:
        signature_img = Image.open(signature_file)
        st.session_state.signature_image = signature_img
        
        st.success("✅ 서명 이미지 업로드 완료")
        
        # 서명 미리보기
        preview_img = resize_signature(signature_img, 120, 60)
        st.image(preview_img, caption="업로드된 서명")
        
        # 서명 크기 조정
        st.subheader("서명 크기 조정")
        sig_width = st.slider("서명 너비", 50, 300, 150, key="sig_width")
        sig_height = st.slider("서명 높이", 25, 150, 75, key="sig_height")

# 메인 영역
if pdf_file:
    # PDF 바이트 데이터 저장
    pdf_bytes = pdf_file.read()
    
    # PDF를 이미지로 변환
    if st.session_state.pdf_images is None:
        with st.spinner("PDF를 이미지로 변환 중..."):
            images, page_count = convert_pdf_to_images(pdf_bytes)
            if images:
                st.session_state.pdf_images = images
                st.session_state.pdf_bytes = pdf_bytes
    
    if st.session_state.pdf_images:
        st.success(f"✅ PDF 변환 완료 ({len(st.session_state.pdf_images)}페이지)")
        
        # 페이지 선택
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            current_page = st.selectbox(
                "페이지 선택",
                range(len(st.session_state.pdf_images)),
                format_func=lambda x: f"페이지 {x + 1}",
                key="page_selector"
            )
            st.session_state.current_page = current_page
        
        # 현재 페이지 이미지
        current_image = st.session_state.pdf_images[current_page]
        
        # 서명 위치 선택 영역
        st.subheader(f"📄 페이지 {current_page + 1}")
        
        if st.session_state.signature_image:
            st.info("💡 이미지를 클릭하여 서명을 추가할 위치를 선택하세요")
            
            # 이미지 표시 및 클릭 위치 받기
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                # 현재 페이지에 이미 서명이 있다면 보여주기
                display_image = current_image
                if current_page in st.session_state.signature_positions:
                    sig_size = (
                        st.session_state.get('sig_width', 150),
                        st.session_state.get('sig_height', 75)
                    )
                    display_image = add_signature_to_image(
                        current_image,
                        st.session_state.signature_image,
                        st.session_state.signature_positions[current_page],
                        sig_size
                    )
                
                st.write("📏 **이미지 크기**: {} × {} 픽셀".format(current_image.width, current_image.height))
                st.write("👆 **아래 이미지를 클릭하세요!**")
                
                # Plotly를 사용한 클릭 가능한 이미지
                fig = go.Figure()
                
                # 이미지 추가
                fig.add_layout_image(
                    dict(
                        source=display_image,
                        xref="x",
                        yref="y",
                        x=0,
                        y=current_image.height,
                        sizex=current_image.width,
                        sizey=current_image.height,
                        sizing="stretch",
                        opacity=1,
                        layer="below"
                    )
                )
                
                # 축 설정
                fig.update_xaxes(
                    showgrid=False,
                    zeroline=False,
                    range=[0, current_image.width],
                    showticklabels=True
                )
                fig.update_yaxes(
                    showgrid=False,
                    zeroline=False,
                    range=[0, current_image.height],
                    showticklabels=True,
                    scaleanchor="x",
                    scaleratio=1
                )
                
                # 레이아웃 설정
                fig.update_layout(
                    title="서명 위치를 클릭하세요",
                    xaxis_title="X 좌표",
                    yaxis_title="Y 좌표",
                    width=min(800, current_image.width + 100),
                    height=min(600, current_image.height + 100),
                    margin=dict(l=50, r=50, t=50, b=50)
                )
                
                # Streamlit에서 plotly 차트 표시 및 클릭 이벤트 받기
                clicked_data = st.plotly_chart(
                    fig, 
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="points",
                    key=f"plotly_page_{current_page}"
                )
                
                # 클릭 좌표 처리
                if clicked_data and clicked_data['selection']['points']:
                    point = clicked_data['selection']['points'][0]
                    clicked_x = int(point['x'])
                    clicked_y = int(current_image.height - point['y'])  # Y축 뒤집기
                    
                    # 서명 크기를 고려한 위치 조정
                    sig_width = st.session_state.get('sig_width', 150)
                    sig_height = st.session_state.get('sig_height', 75)
                    
                    actual_x = min(clicked_x, current_image.width - sig_width)
                    actual_y = min(clicked_y, current_image.height - sig_height)
                    actual_x = max(0, actual_x)
                    actual_y = max(0, actual_y)
                    
                    st.success(f"📍 **선택된 위치**: ({actual_x}, {actual_y})")
                    
                    # 실시간 미리보기
                    with st.container():
                        st.write("🔍 **서명 미리보기**")
                        sig_size = (sig_width, sig_height)
                        preview_img = add_signature_to_image(
                            current_image,
                            st.session_state.signature_image,
                            (actual_x, actual_y),
                            sig_size
                        )
                        st.image(preview_img, caption="서명이 추가된 미리보기")
                    
                    # 서명 추가 버튼
                    col_add, col_clear = st.columns(2)
                    with col_add:
                        if st.button(f"✅ 이 위치에 서명 추가", key=f"confirm_add_{current_page}"):
                            st.session_state.signature_positions[current_page] = (actual_x, actual_y)
                            st.success(f"✅ 페이지 {current_page + 1}에 서명이 추가되었습니다!")
                            st.rerun()
                    
                    with col_clear:
                        if st.button("🔄 선택 초기화", key=f"clear_selection_{current_page}"):
                            st.rerun()
                
                # 서명 제거 버튼
                if current_page in st.session_state.signature_positions:
                    st.markdown("---")
                    current_pos = st.session_state.signature_positions[current_page]
                    st.info(f"📌 현재 서명 위치: ({current_pos[0]}, {current_pos[1]})")
                    
                    if st.button(f"🗑️ 페이지 {current_page + 1} 서명 제거", key=f"remove_{current_page}"):
                        del st.session_state.signature_positions[current_page]
                        st.success(f"🗑️ 페이지 {current_page + 1}의 서명이 제거되었습니다!")
                        st.rerun()
                
                # 수동 좌표 입력 옵션 (접힌 상태로)
                with st.expander("⌨️ 수동 좌표 입력 (정확한 좌표가 필요한 경우)"):
                    manual_col1, manual_col2 = st.columns(2)
                    with manual_col1:
                        max_x = max(0, current_image.width - st.session_state.get('sig_width', 150))
                        manual_x = st.number_input(
                            "X 좌표 (가로)", 
                            min_value=0, 
                            max_value=max_x,
                            value=min(50, max_x),
                            key=f"manual_x_pos_{current_page}"
                        )
                    with manual_col2:
                        max_y = max(0, current_image.height - st.session_state.get('sig_height', 75))
                        manual_y = st.number_input(
                            "Y 좌표 (세로)", 
                            min_value=0, 
                            max_value=max_y,
                            value=min(50, max_y),
                            key=f"manual_y_pos_{current_page}"
                        )
                    
                    col_manual_add, col_manual_preview = st.columns(2)
                    with col_manual_add:
                        if st.button(f"📝 수동 좌표로 서명 추가", key=f"manual_add_{current_page}"):
                            st.session_state.signature_positions[current_page] = (manual_x, manual_y)
                            st.success(f"✅ 페이지 {current_page + 1}에 서명이 추가되었습니다!")
                            st.rerun()
                    
                    with col_manual_preview:
                        if st.button(f"👁️ 수동 좌표 미리보기", key=f"manual_preview_{current_page}"):
                            sig_size = (
                                st.session_state.get('sig_width', 150),
                                st.session_state.get('sig_height', 75)
                            )
                            preview_img = add_signature_to_image(
                                current_image,
                                st.session_state.signature_image,
                                (manual_x, manual_y),
                                sig_size
                            )
                            st.image(preview_img, caption="수동 좌표 미리보기")
        
        # 서명된 페이지 목록
        if st.session_state.signature_positions:
            st.subheader("📋 서명이 추가된 페이지")
            signed_pages = list(st.session_state.signature_positions.keys())
            signed_pages.sort()
            
            for page_idx in signed_pages:
                pos = st.session_state.signature_positions[page_idx]
                st.write(f"• 페이지 {page_idx + 1}: 위치 ({pos[0]}, {pos[1]})")
        
        # 다운로드 섹션
        if st.session_state.signature_positions and st.session_state.signature_image:
            st.markdown("---")
            st.subheader("💾 다운로드")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # PDF로 다운로드
                if st.button("📄 PDF로 다운로드", key="download_pdf"):
                    with st.spinner("PDF 생성 중..."):
                        pdf_buffer = create_pdf_with_signature_pymupdf(
                            st.session_state.pdf_bytes,
                            st.session_state.signature_positions,
                            st.session_state.signature_image
                        )
                        
                        if pdf_buffer:
                            st.download_button(
                                label="📥 서명된 PDF 다운로드",
                                data=pdf_buffer.getvalue(),
                                file_name="signed_document.pdf",
                                mime="application/pdf"
                            )
                        else:
                            st.error("PDF 생성에 실패했습니다.")
            
            with col2:
                # 현재 페이지를 이미지로 다운로드
                if current_page in st.session_state.signature_positions:
                    if st.button("🖼️ 현재 페이지 이미지 다운로드", key="download_image"):
                        sig_size = (
                            st.session_state.get('sig_width', 150),
                            st.session_state.get('sig_height', 75)
                        )
                        result_image = add_signature_to_image(
                            current_image,
                            st.session_state.signature_image,
                            st.session_state.signature_positions[current_page],
                            sig_size
                        )
                        
                        # 이미지를 바이트로 변환
                        img_buffer = io.BytesIO()
                        result_image.save(img_buffer, format='PNG')
                        img_buffer.seek(0)
                        
                        st.download_button(
                            label="📥 서명된 페이지 이미지 다운로드",
                            data=img_buffer.getvalue(),
                            file_name=f"signed_page_{current_page + 1}.png",
                            mime="image/png"
                        )

else:
    # 시작 화면
    st.markdown("""
    ## 🚀 사용 방법
    
    1. **PDF 파일 업로드**: 왼쪽 사이드바에서 서명을 추가할 PDF 파일을 선택하세요
    2. **서명 이미지 업로드**: 전자서명 이미지 파일을 업로드하세요 (PNG 권장)
    3. **서명 크기 조정**: 사이드바에서 서명의 크기를 조정하세요
    4. **🖱️ 그래프 클릭**: Plotly 그래프에서 서명을 추가할 위치를 직접 클릭하세요!
    5. **실시간 미리보기**: 클릭한 위치의 서명 미리보기를 즉시 확인하세요
    6. **서명 확정**: '✅ 이 위치에 서명 추가' 버튼으로 서명을 적용하세요
    7. **다운로드**: 완성된 문서를 PDF 또는 이미지 형태로 다운로드하세요
    
    ### 💡 사용 팁
    - **🖱️ 그래프 클릭**: Plotly 그래프의 이미지를 직접 클릭하면 정확한 좌표가 선택됩니다
    - **📊 좌표 확인**: X, Y 축을 통해 정확한 위치를 확인할 수 있습니다
    - **실시간 미리보기**: 클릭하면 바로 서명이 어떻게 보일지 확인할 수 있습니다
    - **수동 입력**: 정확한 좌표가 필요하면 '수동 좌표 입력' 섹션을 사용하세요
    - **서명 이미지**: 투명 배경의 PNG 파일을 사용하면 더 자연스럽습니다
    - **여러 페이지**: 다른 페이지로 이동하여 각각 다른 위치에 서명을 추가할 수 있습니다
    - **크기 조정**: 사이드바에서 서명 크기를 문서에 맞게 조정하세요
    
    ### ⚡ 새로운 기능
    - **🖱️ Plotly 클릭**: 안정적이고 정확한 마우스 클릭 위치 선택
    - **📊 좌표 축 표시**: X, Y 좌표가 명확하게 표시되는 그래프 형태
    - **실시간 미리보기**: 클릭 즉시 서명이 적용된 결과 확인
    - **자동 경계 조정**: 서명이 이미지 밖으로 나가지 않도록 자동 조정
    - **현재 위치 표시**: 이미 추가된 서명의 정확한 좌표 표시
    - **빠른 변환**: PyMuPDF 사용으로 더 빠르고 안정적인 PDF 처리
    - **고해상도**: 더 선명한 이미지 변환
    """)

# 설치 안내
with st.expander("📋 설치 가이드"):
    st.markdown("""
    ### 🔧 필수 라이브러리 설치
    
    ```bash
    pip install streamlit
    pip install pillow
    pip install PyMuPDF
    pip install reportlab
    pip install plotly
    ```
    
    **또는 requirements.txt 사용:**
    ```bash
    pip install -r requirements.txt
    ```
    
    ### ✅ 장점
    - **간단한 설치**: poppler 등 추가 시스템 dependency 불필요
    - **빠른 처리**: PyMuPDF의 효율적인 PDF 처리
    - **안정성**: 크로스 플랫폼 호환성
    - **고품질**: 고해상도 이미지 변환
    
    ### 🚀 실행
    ```bash
    streamlit run app.py
    ```
    """)

st.markdown("---")
st.markdown("*PyMuPDF를 사용하여 더 안정적이고 빠른 PDF 처리를 제공합니다.*")
