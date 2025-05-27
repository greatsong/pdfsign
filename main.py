import streamlit as st
import io
from PIL import Image, ImageDraw
import pdf2image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.utils import ImageReader
import tempfile
import os

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
if 'signature_image' not in st.session_state:
    st.session_state.signature_image = None
if 'signature_positions' not in st.session_state:
    st.session_state.signature_positions = {}
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0

def convert_pdf_to_images(pdf_file):
    """PDF를 이미지로 변환"""
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_file.read())
            tmp_file_path = tmp_file.name
        
        # PDF를 이미지로 변환
        images = pdf2image.convert_from_path(tmp_file_path, dpi=150)
        
        # 임시 파일 삭제
        os.unlink(tmp_file_path)
        
        return images
    except Exception as e:
        st.error(f"PDF 변환 중 오류가 발생했습니다: {str(e)}")
        return None

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

def create_pdf_with_signature(original_images, signature_positions, signature_img):
    """서명이 추가된 PDF 생성"""
    # 메모리 버퍼 생성
    buffer = io.BytesIO()
    
    # 첫 번째 페이지 크기 기준으로 PDF 생성
    first_image = original_images[0]
    pdf_width = first_image.width * 72 / 150  # DPI 150 기준
    pdf_height = first_image.height * 72 / 150
    
    c = canvas.Canvas(buffer, pagesize=(pdf_width, pdf_height))
    
    for i, img in enumerate(original_images):
        # 현재 페이지에 서명이 있는지 확인
        if i in signature_positions:
            img_with_signature = add_signature_to_image(
                img, signature_img, signature_positions[i]
            )
        else:
            img_with_signature = img
        
        # 이미지를 임시 버퍼에 저장
        img_buffer = io.BytesIO()
        img_with_signature.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        # PDF에 이미지 추가
        c.drawImage(ImageReader(img_buffer), 0, 0, width=pdf_width, height=pdf_height)
        
        # 다음 페이지 (마지막 페이지가 아닌 경우)
        if i < len(original_images) - 1:
            c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer

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
        st.image(signature_img, caption="업로드된 서명", width=150)

# 메인 영역
if pdf_file:
    # PDF를 이미지로 변환
    if st.session_state.pdf_images is None:
        with st.spinner("PDF를 이미지로 변환 중..."):
            st.session_state.pdf_images = convert_pdf_to_images(pdf_file)
    
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
                    display_image = add_signature_to_image(
                        current_image,
                        st.session_state.signature_image,
                        st.session_state.signature_positions[current_page]
                    )
                
                st.image(display_image, use_column_width=True)
                
                # 서명 위치 입력
                col_x, col_y = st.columns(2)
                with col_x:
                    x_pos = st.number_input(
                        "X 좌표", 
                        min_value=0, 
                        max_value=current_image.width-150,
                        value=50,
                        key=f"x_pos_{current_page}"
                    )
                with col_y:
                    y_pos = st.number_input(
                        "Y 좌표", 
                        min_value=0, 
                        max_value=current_image.height-75,
                        value=50,
                        key=f"y_pos_{current_page}"
                    )
                
                # 서명 추가/제거 버튼
                col_add, col_remove = st.columns(2)
                with col_add:
                    if st.button(f"📝 페이지 {current_page + 1}에 서명 추가", key=f"add_{current_page}"):
                        st.session_state.signature_positions[current_page] = (x_pos, y_pos)
                        st.success(f"페이지 {current_page + 1}에 서명이 추가되었습니다!")
                        st.rerun()
                
                with col_remove:
                    if current_page in st.session_state.signature_positions:
                        if st.button(f"🗑️ 페이지 {current_page + 1} 서명 제거", key=f"remove_{current_page}"):
                            del st.session_state.signature_positions[current_page]
                            st.success(f"페이지 {current_page + 1}의 서명이 제거되었습니다!")
                            st.rerun()
        
        # 서명된 페이지 목록
        if st.session_state.signature_positions:
            st.subheader("📋 서명이 추가된 페이지")
            signed_pages = list(st.session_state.signature_positions.keys())
            signed_pages.sort()
            st.write(f"페이지: {', '.join([str(p+1) for p in signed_pages])}")
        
        # 다운로드 섹션
        if st.session_state.signature_positions and st.session_state.signature_image:
            st.markdown("---")
            st.subheader("💾 다운로드")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # PDF로 다운로드
                if st.button("📄 PDF로 다운로드", key="download_pdf"):
                    with st.spinner("PDF 생성 중..."):
                        pdf_buffer = create_pdf_with_signature(
                            st.session_state.pdf_images,
                            st.session_state.signature_positions,
                            st.session_state.signature_image
                        )
                        
                        st.download_button(
                            label="📥 서명된 PDF 다운로드",
                            data=pdf_buffer.getvalue(),
                            file_name="signed_document.pdf",
                            mime="application/pdf"
                        )
            
            with col2:
                # 현재 페이지를 이미지로 다운로드
                if current_page in st.session_state.signature_positions:
                    if st.button("🖼️ 현재 페이지 이미지 다운로드", key="download_image"):
                        result_image = add_signature_to_image(
                            current_image,
                            st.session_state.signature_image,
                            st.session_state.signature_positions[current_page]
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
    ## 사용 방법
    
    1. **PDF 파일 업로드**: 왼쪽 사이드바에서 서명을 추가할 PDF 파일을 선택하세요
    2. **서명 이미지 업로드**: 전자서명 이미지 파일을 업로드하세요 (PNG 권장)
    3. **위치 선택**: 페이지를 선택하고 서명을 추가할 위치의 좌표를 입력하세요
    4. **서명 추가**: '서명 추가' 버튼을 클릭하여 원하는 위치에 서명을 추가하세요
    5. **다운로드**: 완성된 문서를 PDF 또는 이미지 형태로 다운로드하세요
    
    ### 💡 팁
    - 서명 이미지는 투명 배경의 PNG 파일을 사용하면 더 자연스럽습니다
    - 여러 페이지에 서명을 추가할 수 있습니다
    - 좌표는 이미지의 왼쪽 상단을 (0,0) 기준으로 합니다
    """)

# 필수 라이브러리 설치 안내
with st.expander("📋 필수 라이브러리 설치"):
    st.code("""
pip install streamlit
pip install pillow
pip install pdf2image
pip install reportlab

# PDF 변환을 위한 추가 설치 (시스템별)
# Ubuntu/Debian:
sudo apt-get install poppler-utils

# macOS:
brew install poppler

# Windows:
# poppler-utils for Windows 다운로드 필요
    """, language="bash")
