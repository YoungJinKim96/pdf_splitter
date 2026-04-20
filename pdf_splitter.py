import streamlit as st
from pypdf import PdfReader, PdfWriter
import io
import zipfile

st.set_page_config(page_title="PDF 분할기", page_icon="✂️", layout="wide")

st.title("✂️ PDF 분할기")
st.caption("PDF를 업로드하고 원하는 페이지를 그룹으로 나눠 분할하세요.")

# ── 세션 상태 초기화 ─────────────────────────────────────────
if "groups" not in st.session_state:
    st.session_state.groups = []
if "step" not in st.session_state:
    st.session_state.step = "selecting"

# ── PDF 업로드 ───────────────────────────────────────────────
uploaded_file = st.file_uploader("📂 PDF 파일을 업로드하세요", type=["pdf"])

if uploaded_file:
    reader = PdfReader(uploaded_file)
    total_pages = len(reader.pages)
    base_name = uploaded_file.name.replace(".pdf", "")

    st.success(f"✅ **{uploaded_file.name}** — 총 **{total_pages}페이지**")
    st.divider()

    # ── 이미 배정된 페이지 계산 ─────────────────────────────
    assigned_pages = set()
    for g in st.session_state.groups:
        assigned_pages.update(g["pages"])
    remaining_pages = [i for i in range(total_pages) if i not in assigned_pages]

    # ══════════════════════════════════════════════════════════
    # 그룹 선택 단계
    # ══════════════════════════════════════════════════════════
    if st.session_state.step == "selecting":

        current_group_num = len(st.session_state.groups) + 1

        # ── 이미 구성된 그룹 현황 ────────────────────────────
        if st.session_state.groups:
            st.subheader("📋 현재까지 구성된 그룹")
            for i, g in enumerate(st.session_state.groups):
                page_labels = ", ".join(f"p.{p+1}" for p in g["pages"])
                col1, col2 = st.columns([6, 1])
                col1.markdown(f"**그룹 {i+1}** → {page_labels}")
                if col2.button("🗑️ 삭제", key=f"del_{i}"):
                    st.session_state.groups.pop(i)
                    st.rerun()
            st.divider()

        # ── 남은 페이지 없으면 자동으로 완료 단계로 ─────────
        if not remaining_pages and st.session_state.groups:
            st.session_state.step = "done"
            st.rerun()

        # ── 현재 그룹 선택 UI ────────────────────────────────
        st.subheader(f"📁 그룹 {current_group_num}에 포함할 페이지를 선택하세요")
        if assigned_pages:
            st.caption(f"🔒 배정 완료된 페이지는 잠금 | 남은 페이지: {[p+1 for p in remaining_pages]}")

        cols_per_row = 10
        selected_now = []
        rows = [remaining_pages[i:i+cols_per_row] for i in range(0, len(remaining_pages), cols_per_row)]

        for row in rows:
            cols = st.columns(cols_per_row)
            for j, page_idx in enumerate(row):
                if cols[j].checkbox(f"p.{page_idx+1}", key=f"cur_p{page_idx}"):
                    selected_now.append(page_idx)

        if selected_now:
            st.info(f"✅ 그룹 {current_group_num} 선택 중: {[p+1 for p in sorted(selected_now)]}")
        else:
            st.caption("페이지를 선택해주세요.")

        st.divider()
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button(
                f"➕ 그룹 {current_group_num} 확정하고 다음 그룹 설정",
                type="primary",
                use_container_width=True,
                disabled=len(selected_now) == 0,
            ):
                st.session_state.groups.append({"pages": sorted(selected_now)})
                st.rerun()

        with col2:
            finish_disabled = len(st.session_state.groups) == 0 and len(selected_now) == 0
            if st.button(
                "✅ 분할 설정 완료",
                use_container_width=True,
                disabled=finish_disabled,
            ):
                if selected_now:
                    st.session_state.groups.append({"pages": sorted(selected_now)})
                st.session_state.step = "done"
                st.rerun()

        with col3:
            if st.session_state.groups:
                if st.button("🔄 처음부터 다시", use_container_width=True):
                    st.session_state.groups = []
                    st.session_state.step = "selecting"
                    st.rerun()

    # ══════════════════════════════════════════════════════════
    # 완료 단계: 요약 + 다운로드
    # ══════════════════════════════════════════════════════════
    elif st.session_state.step == "done":

        num_groups = len(st.session_state.groups)
        st.subheader(f"🎉 총 {num_groups}개의 PDF로 분할하겠습니다")

        def make_filename(g):
            return f"{base_name}_pages({'-'.join(str(p+1) for p in g['pages'])}).pdf"

        def make_pdf_bytes(page_indices):
            writer = PdfWriter()
            for idx in page_indices:
                writer.add_page(reader.pages[idx])
            buf = io.BytesIO()
            writer.write(buf)
            return buf.getvalue()

        # 분할 요약
        for i, g in enumerate(st.session_state.groups):
            page_labels = ", ".join(f"p.{p+1}" for p in g["pages"])
            st.markdown(f"- **그룹 {i+1}** ({len(g['pages'])}페이지: {page_labels}) → `{make_filename(g)}`")

        st.divider()

        # ── 다운로드 방식 선택 ───────────────────────────────
        st.subheader("⬇️ 다운로드 방식 선택")
        download_mode = st.radio(
            "",
            ["📦 ZIP으로 한번에 받기", "📄 파일 개별로 받기"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if download_mode == "📦 ZIP으로 한번에 받기":
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for g in st.session_state.groups:
                    zf.writestr(make_filename(g), make_pdf_bytes(g["pages"]))

            st.download_button(
                label=f"⬇️ ZIP 다운로드  ({num_groups}개 파일)",
                data=zip_buffer.getvalue(),
                file_name=f"{base_name}_분할.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

        else:
            st.caption("각 파일을 개별적으로 다운로드하세요.")
            for i, g in enumerate(st.session_state.groups):
                page_labels = ", ".join(f"p.{p+1}" for p in g["pages"])
                st.download_button(
                    label=f"⬇️ 그룹 {i+1} 다운로드  ({page_labels})",
                    data=make_pdf_bytes(g["pages"]),
                    file_name=make_filename(g),
                    mime="application/pdf",
                    key=f"dl_{i}",
                    use_container_width=True,
                )

        st.divider()
        if st.button("🔄 처음부터 다시", use_container_width=True):
            st.session_state.groups = []
            st.session_state.step = "selecting"
            st.rerun()

else:
    st.info("👆 PDF 파일을 업로드하면 분할 옵션이 나타납니다.")
    st.markdown("""
    ### 사용 방법
    1. **PDF 업로드**
    2. **그룹 1 페이지 선택** → `그룹 1 확정하고 다음 그룹 설정` 클릭
    3. **그룹 2 페이지 선택** → 확정
    4. 원하는 만큼 반복 후 **분할 설정 완료** 클릭
    5. **ZIP** 또는 **개별 파일**로 다운로드
    """)
