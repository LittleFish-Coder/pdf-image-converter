import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import zipfile
import os

# --- 基本設定 ---
st.set_page_config(
    page_title="PDF & Image Converter",
    page_icon="📄",
)

# --- Helper Functions ---

# 將 PDF 頁面轉換為圖片 (PNG 或 JPG)
def pdf_to_images(pdf_bytes, output_format="png", dpi=200):
    """
    將 PDF 文件轉換為指定格式的圖片列表。

    Args:
        pdf_bytes (bytes): PDF 文件的 bytes 內容。
        output_format (str): 輸出圖片格式 ('png' or 'jpg').
        dpi (int): 圖片的 DPI (解析度).

    Returns:
        list: 包含 (檔名, 圖片 bytes) 的元組列表。
               如果發生錯誤則返回 None。
    """
    images = []
    try:
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        zoom_matrix = fitz.Matrix(dpi / 72, dpi / 72) # 計算縮放矩陣

        for page_num in range(len(pdf_doc)):
            page = pdf_doc.load_page(page_num)
            pix = page.get_pixmap(matrix=zoom_matrix)
            img_bytes_io = io.BytesIO()

            # 使用 Pillow 儲存，可以更好地控制 JPG 品質
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            if output_format.lower() == "png":
                img.save(img_bytes_io, format="PNG")
                filename = f"page_{page_num + 1}.png"
                img_bytes = img_bytes_io.getvalue()
            elif output_format.lower() == "jpg":
                # 移除 Alpha 通道（如果有的話）以儲存為 JPG
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(img_bytes_io, format="JPEG", quality=95) # 可調整 quality
                filename = f"page_{page_num + 1}.jpg"
                img_bytes = img_bytes_io.getvalue()
            else:
                st.error(f"不支援的格式: {output_format}")
                return None

            images.append((filename, img_bytes))

        pdf_doc.close()
        return images
    except Exception as e:
        st.error(f"處理 PDF 時發生錯誤: {e}")
        return None

# 將多張圖片合併為一個 PDF
def images_to_pdf(image_files, output_filename="output.pdf"):
    """
    將上傳的圖片檔案列表合併為一個 PDF 文件。

    Args:
        image_files (list): Streamlit UploadedFile 物件的列表。
        output_filename (str): 輸出的 PDF 檔名。

    Returns:
        bytes: PDF 文件的 bytes 內容。
               如果沒有圖片或發生錯誤則返回 None。
    """
    if not image_files:
        st.warning("請至少上傳一張圖片。")
        return None

    pil_images = []
    try:
        # 讀取並轉換所有圖片
        for uploaded_file in image_files:
            try:
                img = Image.open(uploaded_file)
                # 確保是 RGB 模式，以便儲存為 PDF
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                elif img.mode == 'P': # 處理調色板模式
                     img = img.convert('RGB')
                elif img.mode == 'L': # 處理灰度模式
                     img = img.convert('RGB')

                pil_images.append(img)
            except Exception as e:
                st.error(f"無法讀取圖片 '{uploaded_file.name}': {e}")
                # 選擇性跳過錯誤檔案或中止
                # return None

        if not pil_images:
             st.error("未能成功讀取任何圖片。")
             return None

        # 將圖片儲存為 PDF
        pdf_buffer = io.BytesIO()
        # 使用第一張圖片的 save 方法，並將其餘圖片附加進去
        pil_images[0].save(
            pdf_buffer,
            "PDF",
            resolution=100.0, # PDF 內部解析度
            save_all=True,    # 儲存所有圖片
            append_images=pil_images[1:] # 附加其餘圖片
        )
        return pdf_buffer.getvalue()

    except Exception as e:
        st.error(f"合併圖片為 PDF 時發生錯誤: {e}")
        return None

# --- UI 介面 ---

st.title("PDF & Image Converter")
st.markdown("將 PDF 轉換為圖片，或將多張圖片合併為 PDF 檔案。")

# 使用 Tabs 來切換模式
tab1, tab2 = st.tabs(["📄 PDF ➔ 圖片", "🖼️ 圖片 ➔ PDF"])

# --- Tab 1: PDF to Images ---
with tab1:
    st.header("將 PDF 轉換為圖片")
    st.markdown("上傳您的 PDF 檔案，選擇輸出格式和解析度，即可轉換為多張圖片並打包下載。")

    uploaded_pdf = st.file_uploader("選擇一個 PDF 檔案", type="pdf", key="pdf_uploader")

    col1, col2 = st.columns(2)
    with col1:
        output_format = st.radio(
            "選擇輸出圖片格式:",
            ('PNG', 'JPG'),
            key="pdf_to_img_format",
            horizontal=True # 水平排列選項
        )
    with col2:
        dpi = st.slider(
            "選擇圖片解析度 (DPI):",
            min_value=72,
            max_value=600,
            value=200, # 預設值
            step=10,
            key="pdf_dpi"
        )

    convert_pdf_button = st.button("開始轉換 PDF", key="convert_pdf", type="primary")

    if convert_pdf_button and uploaded_pdf is not None:
        pdf_bytes = uploaded_pdf.getvalue()
        with st.spinner(f'正在將 PDF 轉換為 {output_format} 圖片...'):
            image_data = pdf_to_images(pdf_bytes, output_format.lower(), dpi)

        if image_data:
            st.success(f"轉換完成！共產生 {len(image_data)} 張圖片。")

            # 建立 ZIP 檔案供下載
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for filename, img_bytes in image_data:
                    zf.writestr(filename, img_bytes)
            zip_buffer.seek(0) # 重要：將指標移回開頭

            # 提供下載按鈕
            st.download_button(
                label=f"下載所有 {output_format} 圖片 (ZIP)",
                data=zip_buffer,
                file_name=f"{os.path.splitext(uploaded_pdf.name)[0]}_images.zip",
                mime="application/zip",
                key="download_zip"
            )

            # (選擇性) 顯示前幾張圖片預覽
            st.subheader("預覽 (最多顯示 5 張):")
            preview_cols = st.columns(5) # 一行最多顯示5張
            for i, (filename, img_bytes) in enumerate(image_data[:5]):
                 with preview_cols[i % 5]:
                    st.image(img_bytes, caption=filename, use_column_width='auto')

        else:
            st.error("PDF 轉換失敗，請檢查檔案或錯誤訊息。")

    elif convert_pdf_button and uploaded_pdf is None:
        st.warning("請先上傳一個 PDF 檔案。")


# --- Tab 2: Images to PDF ---
with tab2:
    st.header("將多張圖片合併為 PDF")
    st.markdown("上傳多張 PNG 或 JPG/JPEG 圖片，它們將按照檔名順序合併成一個 PDF 檔案。")

    uploaded_images = st.file_uploader(
        "選擇圖片檔案 (可多選)",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="image_uploader"
    )

    output_pdf_name = st.text_input("設定輸出 PDF 檔名:", value="combined_images.pdf", key="output_name")

    convert_images_button = st.button("開始合併圖片", key="convert_images", type="primary")

    if convert_images_button and uploaded_images:
        # 嘗試根據檔名排序圖片 (如果使用者在意順序)
        # 注意：Streamlit 上傳順序可能不穩定，檔名排序較可靠
        uploaded_images.sort(key=lambda f: f.name)

        st.info(f"準備合併 {len(uploaded_images)} 張圖片...")
        # 顯示被合併的圖片順序 (檔名)
        st.write("圖片合併順序 (根據檔名排序):")
        st.json([f.name for f in uploaded_images])


        with st.spinner('正在合併圖片為 PDF...'):
            pdf_bytes = images_to_pdf(uploaded_images, output_pdf_name)

        if pdf_bytes:
            st.success("圖片成功合併為 PDF！")
            st.download_button(
                label=f"下載 {output_pdf_name}",
                data=pdf_bytes,
                file_name=output_pdf_name,
                mime="application/pdf",
                key="download_pdf"
            )
        else:
            st.error("圖片合併失敗，請檢查圖片檔案或錯誤訊息。")

    elif convert_images_button and not uploaded_images:
        st.warning("請先上傳至少一張圖片檔案。")

st.markdown("Made by [LittleFish-Coder 🐟](https://github.com/LittleFish-Coder)")