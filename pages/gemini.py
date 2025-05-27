import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageOps
import io
from streamlit_drawable_canvas import st_canvas

# --- 유틸리티 함수 ---
def make_bg_transparent(pil_img, threshold=240):
    """
    PIL 이미지를 받아 흰색 배경을 투명하게 만듭니다.
    threshold 이상의 R, G, B 값을 가진 픽셀을 투명하게 처리합니다.
    """
    img = pil_img.convert("RGBA")
    datas = img.getdata()
    newData = []
    for item in datas:
        if item[0] >= threshold and item[1] >= threshold and item[2] >= threshold:
            newData.append((255, 255, 255, 0))  # 투명
        else:
            newData.append(item)
    img.putdata(newData)
    return img

# --- 스트림릿 앱 ---
st.set_page_config(layout="wide")
st.title("✍️ PDF에 클릭으로 전자서명 합치기")

# --- 사이드바: 파일 업로드 및 옵션 ---
with st.sidebar:
    st.header("파일 및 옵션 설정")
    uploaded_pdf = st.file_uploader("1. PDF 파일을 업로드하세요", type="pdf")
    uploaded_signature_img = st.file_uploader("2. 서명 이미지 파일을 업로드하세요", type=["png", "jpg", "jpeg"])

    selected_page_num = 0
    pdf_doc = None
    original_sig_pil = None
    sig_processed_bytes = None

    if uploaded_pdf:
        pdf_bytes = uploaded_pdf.read()
        try:
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(pdf_doc)
            selected_page_num = st.number_input(f"3. 서명할 페이지 선택 (0 ~ {total_pages-1})", min_value=0, max_value=total_pages-1, value=0)
        except Exception as e:
            st.error(f"PDF 로드 오류: {e}")
            pdf_doc = None # 오류 발생 시 pdf_doc 초기화

    if uploaded_signature_img:
        signature_bytes = uploaded_signature_img.read()
        try:
            original_sig_pil = Image.open(io.BytesIO(signature_bytes))
            
            make_transparent = st.checkbox("서명 배경 투명하게 만들기 (흰색 배경 대상)", value=True)
            if make_transparent:
                processed_sig_pil = make_bg_transparent(original_sig_pil.copy())
            else:
                # RGBA로 변환해야 PyMuPDF에서 PNG로 올바르게 처리 가능
                if original_sig_pil.mode != 'RGBA':
                    processed_sig_pil = original_sig_pil.convert('RGBA')
                else:
                    processed_sig_pil = original_sig_pil.copy()

            # Pillow 이미지를 PNG 바이트로 변환
            sig_buffer = io.BytesIO()
            processed_sig_pil.save(sig_buffer, format="PNG")
            sig_processed_bytes = sig_buffer.getvalue()

        except Exception as e:
            st.error(f"서명 이미지 처리 오류: {e}")
            original_sig_pil = None


    signature_width_pdf_pts = st.slider("4. 서명 너비 (PDF 위 실제 크기, pt 단위)", min_value=20, max_value=300, value=100)
    
    # Canvas DPI 설정 (높을수록 Canvas 해상도 증가)
    CANVAS_DPI = 150 # PDF 페이지를 Canvas에 표시할 때의 DPI

# --- 메인 영역: PDF 페이지 표시 및 서명 위치 지정 ---
if pdf_doc and original_sig_pil and sig_processed_bytes:
    try:
        page_to_sign = pdf_doc.load_page(selected_page_num)
        
        # PDF 페이지를 이미지로 변환 (Canvas 배경용)
        pix = page_to_sign.get_pixmap(dpi=CANVAS_DPI)
        page_img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Canvas 설정
        # 실제 PDF 페이지의 가로세로 비율 유지하며 Canvas 크기 조절
        canvas_display_width = 700 # Canvas 디스플레이 너비 고정
        canvas_display_height = int(canvas_display_width * (pix.height / pix.width))

        st.write(f"👇 아래 이미지 위를 **클릭**하여 서명 위치를 지정하세요 (상단 좌측 기준). 페이지: {selected_page_num + 1}/{len(pdf_doc)}")

        # Drawable Canvas
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",  # 거의 사용 안 함 (점 찍기 모드)
            stroke_width=0, # 점 찍기 모드에서는 의미 없음
            stroke_color="red", # 점 색상
            background_image=page_img_pil,
            update_streamlit=True, # 실시간 업데이트
            height=canvas_display_height,
            width=canvas_display_width,
            drawing_mode="point", # 점 찍기 모드
            point_display_radius=5, # 클릭한 점의 반지름
            key=f"canvas_page_{selected_page_num}" # 페이지 변경 시 Canvas 재 초기화
        )

        # 서명 적용 버튼
        if st.button("✅ 선택한 위치에 서명 적용 및 PDF 생성", key="apply_signature"):
            if canvas_result.json_data is not None and canvas_result.json_data["objects"]:
                # 마지막으로 찍은 점의 좌표를 사용
                point = canvas_result.json_data["objects"][-1]
                canvas_x, canvas_y = point["left"], point["top"]

                # Canvas 좌표(픽셀)를 PDF 좌표(pt)로 변환
                # PDF 페이지의 실제 크기 (pt 단위)
                pdf_page_width_pts = page_to_sign.rect.width
                pdf_page_height_pts = page_to_sign.rect.height

                # Canvas에 표시된 이미지의 크기 (픽셀 단위)
                # canvas_display_width, canvas_display_height 사용

                # 스케일링 팩터
                # 실제 PDF 페이지를 CANVAS_DPI로 렌더링한 이미지의 픽셀 크기는 pix.width, pix.height
                # 이 이미지를 canvas_display_width, canvas_display_height로 스케일링해서 보여줬음
                # 따라서 canvas좌표 -> pixmap좌표 -> pdf좌표 순으로 변환
                
                # 1. canvas 좌표 -> pixmap 좌표
                pixmap_x = (canvas_x / canvas_display_width) * pix.width
                pixmap_y = (canvas_y / canvas_display_height) * pix.height

                # 2. pixmap 좌표 -> PDF 좌표 (pt)
                # get_pixmap(dpi=CANVAS_DPI) 이므로, 1인치 = CANVAS_DPI 픽셀 = 72 pt
                # 따라서 1 픽셀 = (72 / CANVAS_DPI) pt
                scale_factor_pix_to_pt = 72.0 / CANVAS_DPI
                
                pdf_x_pt = pixmap_x * scale_factor_pix_to_pt
                pdf_y_pt = pixmap_y * scale_factor_pix_to_pt
                
                st.info(f"선택된 Canvas 좌표: ({canvas_x:.2f}, {canvas_y:.2f} px) -> PDF 좌표: ({pdf_x_pt:.2f}, {pdf_y_pt:.2f} pt)")

                # 서명 이미지 크기 (pt 단위) - 가로 기준, 세로는 비율 유지
                sig_pil_width, sig_pil_height = original_sig_pil.size
                signature_height_pdf_pts = signature_width_pdf_pts * (sig_pil_height / sig_pil_width)

                # PDF에 삽입할 사각형 영역 (x0, y0, x1, y1)
                rect = fitz.Rect(
                    pdf_x_pt,
                    pdf_y_pt,
                    pdf_x_pt + signature_width_pdf_pts,
                    pdf_y_pt + signature_height_pdf_pts
                )

                # 원본 PDF 문서를 다시 열어서 작업 (수정사항 누적 방지)
                final_pdf_doc = fitz.open(stream=uploaded_pdf.getvalue(), filetype="pdf")
                page_to_apply_signature = final_pdf_doc.load_page(selected_page_num)
                
                page_to_apply_signature.insert_image(rect, stream=sig_processed_bytes)

                final_pdf_bytes = final_pdf_doc.tobytes()
                final_pdf_doc.close()

                st.success("🎉 서명이 성공적으로 PDF에 적용되었습니다!")
                
                download_file_name = f"signed_{uploaded_pdf.name}"
                st.download_button(
                    label="📄 서명된 PDF 다운로드",
                    data=final_pdf_bytes,
                    file_name=download_file_name,
                    mime="application/pdf"
                )
            else:
                st.warning("먼저 Canvas 위에 서명할 위치를 클릭해주세요.")
    except Exception as e:
        st.error(f"PDF 처리 중 오류 발생: {e}")
        import traceback
        st.error(traceback.format_exc())

elif not uploaded_pdf:
    st.info("왼쪽 사이드바에서 PDF 파일을 업로드해주세요.")
elif not uploaded_signature_img:
    st.info("왼쪽 사이드바에서 서명 이미지 파일을 업로드해주세요.")

st.markdown("---")
st.markdown("만든이: Gemini (Google AI)")
