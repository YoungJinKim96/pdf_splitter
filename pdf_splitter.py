import streamlit as st
from pypdf import PdfReader, PdfWriter
import io
import zipfile
import fitz  # PyMuPDF

st.set_page_config(page_title="PDF 분할기", page_icon="✂️", layout="wide")

st.title("✂️ PDF 분할기")
st.caption("PDF를 여러 개 업로드하고 탭별로 각각 분할 설정하세요.")

# ── 상수 ─────────────────────────────────────────────────────
GROUP_COLORS = [
    "#4CAF50", "#2196F3", "#FF9800", "#E91E63",
    "#9C27B0", "#00BCD4", "#FF5722", "#607D8B",
]

# ── 유틸 함수 ─────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def generate_thumbnails(file_bytes, dpi=100):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    thumbnails = []
    for page in doc:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        thumbnails.append(pix.tobytes("png"))
    doc.close()
    return thumbnails

def make_pdf_bytes(reader, page_indices):
    writer = PdfWriter()
    for idx in page_indices:
        writer.add_page(reader.pages[idx])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

def make_default_filename(base_name, g):
    return f"{base_name}_pages({'-'.join(str(p+1) for p in g['pages'])})"

# ── 세션 상태 초기화 헬퍼 ────────────────────────────────────
def init_file_state(fkey):
    if fkey not in st.session_state:
        st.session_state[fkey] = {
            "groups": [],
            "step": "selecting",   # selecting | done
        }

# ══════════════════════════════════════════════════════════════
# 파일 업로드 (여러 개)
# ══════════════════════════════════════════════════════════════
uploaded_files = st.file_uploader(
    "📂 PDF 파일을 업로드하세요 (여러 개 선택 가능)",
    type=["pdf"],
    accept_multiple_files=True,
)

if not uploaded_files:
    st.info("👆 PDF 파일을 한 개 이상 업로드하면 탭이 생성됩니다.")
    st.markdown("""
    ### 사용 방법
    1. **PDF 여러 개 업로드** (드래그 또는 다중 선택)
    2. **파일별 탭**에서 각각 그룹 설정
    3. 탭마다 **ZIP 또는 개별 파일**로 다운로드
    """)
    st.stop()

# ── 탭 생성 ──────────────────────────────────────────────────
tab_labels = [f"📄 {f.name[:20]}{'…' if len(f.name)>20 else ''}" for f in uploaded_files]
tabs = st.tabs(tab_labels)

# ══════════════════════════════════════════════════════════════
# 파일별 탭 처리
# ══════════════════════════════════════════════════════════════
for tab, uploaded_file in zip(tabs, uploaded_files):
    with tab:

        fkey = f"file_{uploaded_file.name}_{uploaded_file.size}"
        init_file_state(fkey)
        fstate = st.session_state[fkey]

        file_bytes = uploaded_file.read()
        reader = PdfReader(io.BytesIO(file_bytes))
        total_pages = len(reader.pages)
        base_name = uploaded_file.name.replace(".pdf", "")

        with st.spinner("페이지 미리보기 생성 중..."):
            thumbnails = generate_thumbnails(file_bytes)

        st.success(f"✅ **{uploaded_file.name}** — 총 **{total_pages}페이지**")
        st.divider()

        # ── 배정된 페이지 계산 ───────────────────────────────
        assigned_pages = set()
        for g in fstate["groups"]:
            assigned_pages.update(g["pages"])
        remaining_pages = [i for i in range(total_pages) if i not in assigned_pages]

        # ══════════════════════════════════════════════════════
        # 그룹 선택 단계
        # ══════════════════════════════════════════════════════
        if fstate["step"] == "selecting":

            current_group_num = len(fstate["groups"]) + 1

            # ── 기존 그룹 현황 ───────────────────────────────
            if fstate["groups"]:
                st.subheader("📋 현재까지 구성된 그룹")
                for i, g in enumerate(fstate["groups"]):
                    color = GROUP_COLORS[i % len(GROUP_COLORS)]
                    page_labels = ", ".join(f"p.{p+1}" for p in g["pages"])
                    col1, col2 = st.columns([6, 1])
                    col1.markdown(
                        f"<span style='background:{color};color:white;padding:2px 8px;"
                        f"border-radius:4px;font-weight:bold'>그룹 {i+1}</span> → {page_labels}",
                        unsafe_allow_html=True,
                    )
                    if col2.button("🗑️ 삭제", key=f"{fkey}_del_{i}"):
                        fstate["groups"].pop(i)
                        st.rerun()
                st.divider()

            if not remaining_pages and fstate["groups"]:
                fstate["step"] = "done"
                st.rerun()

            # ── 현재 그룹 선택 UI ────────────────────────────
            current_color = GROUP_COLORS[(current_group_num - 1) % len(GROUP_COLORS)]
            st.markdown(
                f"### 📁 <span style='background:{current_color};color:white;"
                f"padding:3px 10px;border-radius:4px'>그룹 {current_group_num}</span>"
                f" 에 포함할 페이지를 선택하세요",
                unsafe_allow_html=True,
            )
            if assigned_pages:
                st.caption(f"🔒 회색 페이지는 이미 배정됨 | 남은 페이지: {[p+1 for p in remaining_pages]}")

            # ── 썸네일 그리드 ────────────────────────────────
            cols_per_row = 5
            selected_now = []
            all_rows = [
                list(range(total_pages))[i:i+cols_per_row]
                for i in range(0, total_pages, cols_per_row)
            ]

            for row in all_rows:
                cols = st.columns(cols_per_row)
                for j, page_idx in enumerate(row):
                    is_assigned = page_idx in assigned_pages
                    owner_group = next(
                        (gi for gi, g in enumerate(fstate["groups"]) if page_idx in g["pages"]),
                        None,
                    )
                    with cols[j]:
                        if is_assigned and owner_group is not None:
                            oc = GROUP_COLORS[owner_group % len(GROUP_COLORS)]
                            st.markdown(
                                f"<div style='border:3px solid {oc};border-radius:6px;"
                                f"opacity:0.55;overflow:hidden'>",
                                unsafe_allow_html=True,
                            )
                            st.image(thumbnails[page_idx], use_container_width=True)
                            st.markdown("</div>", unsafe_allow_html=True)
                            st.markdown(
                                f"<div style='text-align:center;font-size:11px;"
                                f"color:{oc};font-weight:bold'>그룹{owner_group+1} 배정됨</div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.image(thumbnails[page_idx], use_container_width=True)
                            if st.checkbox(f"p.{page_idx+1}", key=f"{fkey}_p{page_idx}"):
                                selected_now.append(page_idx)

            st.divider()

            if selected_now:
                st.info(f"✅ 그룹 {current_group_num} 선택 중: {[p+1 for p in sorted(selected_now)]}")
            else:
                st.caption("위 썸네일에서 페이지를 체크해주세요.")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(
                    f"➕ 그룹 {current_group_num} 확정하고 다음 그룹 설정",
                    type="primary",
                    use_container_width=True,
                    disabled=len(selected_now) == 0,
                    key=f"{fkey}_confirm",
                ):
                    fstate["groups"].append({"pages": sorted(selected_now)})
                    st.rerun()

            with col2:
                finish_disabled = len(fstate["groups"]) == 0 and len(selected_now) == 0
                if st.button(
                    "✅ 분할 설정 완료",
                    use_container_width=True,
                    disabled=finish_disabled,
                    key=f"{fkey}_finish",
                ):
                    if selected_now:
                        fstate["groups"].append({"pages": sorted(selected_now)})
                    fstate["step"] = "done"
                    st.rerun()

            with col3:
                if fstate["groups"]:
                    if st.button("🔄 처음부터 다시", use_container_width=True, key=f"{fkey}_reset"):
                        fstate["groups"] = []
                        fstate["step"] = "selecting"
                        st.rerun()

        # ══════════════════════════════════════════════════════
        # 완료 단계
        # ══════════════════════════════════════════════════════
        elif fstate["step"] == "done":

            num_groups = len(fstate["groups"])
            st.subheader(f"🎉 총 {num_groups}개의 PDF로 분할하겠습니다")

            # ── 그룹별 썸네일 요약 ───────────────────────────
            for i, g in enumerate(fstate["groups"]):
                color = GROUP_COLORS[i % len(GROUP_COLORS)]
                st.markdown(
                    f"<span style='background:{color};color:white;padding:3px 10px;"
                    f"border-radius:4px;font-weight:bold'>그룹 {i+1}</span>"
                    f" — {len(g['pages'])}페이지",
                    unsafe_allow_html=True,
                )
                thumb_cols = st.columns(min(len(g["pages"]), 10))
                for j, page_idx in enumerate(g["pages"]):
                    with thumb_cols[j]:
                        st.image(thumbnails[page_idx], use_container_width=True)
                        st.caption(f"p.{page_idx+1}")

            st.divider()

            # ── 파일명 수정 ──────────────────────────────────
            st.subheader("✏️ 파일명 수정 (선택사항)")
            st.caption(".pdf 확장자 자동으로 붙습니다.")

            custom_names = []
            for i, g in enumerate(fstate["groups"]):
                page_labels = ", ".join(f"p.{p+1}" for p in g["pages"])
                default_name = make_default_filename(base_name, g)
                col1, col2 = st.columns([1, 3])
                col1.markdown(f"**그룹 {i+1}** ({page_labels})")
                name_input = col2.text_input(
                    label=f"fname",
                    value=default_name,
                    label_visibility="collapsed",
                    key=f"{fkey}_fname_{i}",
                )
                final_name = (name_input.strip() or default_name).removesuffix(".pdf") + ".pdf"
                custom_names.append(final_name)

            st.divider()

            # ── 다운로드 방식 ────────────────────────────────
            st.subheader("⬇️ 다운로드 방식 선택")
            download_mode = st.radio(
                "",
                ["📦 ZIP으로 한번에 받기", "📄 파일 개별로 받기"],
                horizontal=True,
                label_visibility="collapsed",
                key=f"{fkey}_dlmode",
            )

            if download_mode == "📦 ZIP으로 한번에 받기":
                zip_name_input = st.text_input(
                    "ZIP 파일명",
                    value=f"{base_name}_분할",
                    key=f"{fkey}_zipname",
                )
                zip_final_name = (zip_name_input.strip() or f"{base_name}_분할").removesuffix(".zip") + ".zip"

                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, g in enumerate(fstate["groups"]):
                        zf.writestr(custom_names[i], make_pdf_bytes(reader, g["pages"]))

                st.download_button(
                    label=f"⬇️ ZIP 다운로드 ({num_groups}개 파일)",
                    data=zip_buffer.getvalue(),
                    file_name=zip_final_name,
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                    key=f"{fkey}_zip_dl",
                )

            else:
                for i, g in enumerate(fstate["groups"]):
                    page_labels = ", ".join(f"p.{p+1}" for p in g["pages"])
                    st.download_button(
                        label=f"⬇️ 그룹 {i+1} 다운로드 ({page_labels}) → {custom_names[i]}",
                        data=make_pdf_bytes(reader, g["pages"]),
                        file_name=custom_names[i],
                        mime="application/pdf",
                        key=f"{fkey}_dl_{i}",
                        use_container_width=True,
                    )

            st.divider()
            if st.button("🔄 처음부터 다시", use_container_width=True, key=f"{fkey}_reset_done"):
                fstate["groups"] = []
                fstate["step"] = "selecting"
                st.rerun()

