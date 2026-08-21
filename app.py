import io
import numpy as np
import pandas as pd
import streamlit as st
from functions import *
import preprocessing
import matplotlib.pyplot as plt
import networkx as nx
import re
from networkx.exception import PowerIterationFailedConvergence

# Streamlit Cloud는 새 커밋 동기화 시 메인 스크립트만 소스에서 다시 읽고,
# 이미 import된 모듈은 실행 중 프로세스의 옛 버전을 유지할 수 있다(반쪽 배포:
# 새 app.py + 옛 iolib → NameError). 새 이름이 없으면 모듈을 재로드해 자가 수복.
import iolib.download as _iolib_download
if not hasattr(_iolib_download, "render_japan_data_sidebar"):
    import importlib
    importlib.reload(_iolib_download)
render_japan_data_sidebar = _iolib_download.render_japan_data_sidebar


def _render_quadrant_scatter(df_metric, x_col, y_col, title, key):
    """지표 DataFrame(라벨 2열 + 지표 열들)을 4분면 산점도로 그린다.

    x·y 평균 위치에 회색 점선 기준선을 긋고, 사용자가 새로 삽입한 산업
    (`st.session_state.ids_simbol` 에 등록된 이름)은 빨간 점 + 이름 라벨로
    강조한다. FL-BL Plot 과 같은 스타일. `key` 는 다운로드 버튼 위젯 키와
    저장 파일명에 쓰이므로 호출 위치마다 달라야 한다.
    """
    x = pd.to_numeric(df_metric[x_col], errors='coerce')
    y = pd.to_numeric(df_metric[y_col], errors='coerce')
    names = df_metric.iloc[:, 1].astype(str)

    ids_values = [str(v) for sub in st.session_state.get('ids_simbol', {}).values() for v in sub]
    hl = names.isin(ids_values)

    fig, ax = plt.subplots(figsize=(12, 10))
    ax.scatter(x[~hl], y[~hl], facecolors='none', edgecolors='gray', s=100)
    if hl.any():
        ax.scatter(x[hl], y[hl], color='red', s=150, zorder=10)
        for _x, _y, _name in zip(x[hl], y[hl], names[hl]):
            ax.text(_x, _y, _name, color='black', fontsize=16, ha='right')
    ax.axvline(x.mean(), color='gray', linestyle='--', linewidth=1)
    ax.axhline(y.mean(), color='gray', linestyle='--', linewidth=1)
    ax.set_xlabel(x_col, fontsize=14)
    ax.set_ylabel(y_col, fontsize=14)
    ax.set_title(title, fontsize=16)
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    st.download_button(
        label=f"{title} 이미지 다운로드",
        data=buf,
        file_name=f"{key}.png",
        mime="image/png",
        key=f"dl_{key}",
    )


def render_centrality_tabs(cents, weighted=True, key_prefix=""):
    """`calculate_network_centralities` 의 반환 튜플을 6개 하위 탭
    (Degree / Betweenness / Closeness / Eigenvector / Hub&Authority /
    constraints&efficiencies)으로 렌더링한다.

    원래 app.py 안에서 네 번(tn/tbn/n/bn) 똑같이 복사돼 있던 블록을 하나로
    합친 것. Hub&Authority 탭과 constraints&efficiencies 탭에는 표 아래에
    4분면 산점도(Hub-Authority / Constraint-Efficiency)를 함께 그린다.
    `weighted` 는 산점도 제목의 (Weighted)/(Binary) 표기, `key_prefix` 는
    다운로드 버튼 위젯 키 충돌 방지용 — 호출 위치(tn/tbn/n/bn)마다 다르게.
    호출하는 쪽의 `with col...:` 컨텍스트 안에서 그대로 호출하면 된다.
    """
    (df_degree, df_bc, df_cc, df_ev, df_hi, df_kim,
     gd_in_mean, gd_in_std, gd_out_mean, gd_out_std,
     bc_mean, bc_std,
     cc_in_mean, cc_in_std, cc_out_mean, cc_out_std,
     ev_in_mean, ev_in_std, ev_out_mean, ev_out_std,
     hub_mean, hub_std, ah_mean, ah_std,
     const_mean, const_std, eff_mean, eff_std) = cents

    c1, c2, c3, c4, c5, c6 = st.tabs([f"Degree Centrality", 'Betweenness Centrality', "Closeness Centrality", "Eigenvector Centrality", "Hub & Authority", 'constraints&efficiencies'])
    with c1:
        st.dataframe(df_degree)
        st.write("In-Degree: Mean =", gd_in_mean, ", Std =", gd_in_std)
        st.write("Out-Degree: Mean =", gd_out_mean, ", Std =", gd_out_std)

    with c2:
        st.dataframe(
            df_bc,
            column_config={'Betweenness Centrality': st.column_config.NumberColumn('Betweenness Centrality', format='%.12f')}
        )
        st.write("Betweenness Centrality: Mean =", bc_mean, ", Std =", bc_std)

    with c3:
        st.dataframe(
            df_cc,
            column_config={
                'Indegree_Closeness Centrality': st.column_config.NumberColumn('Indegree_Closeness Centrality', format='%.12f'),
                'Outdegree_Closeness Centrality': st.column_config.NumberColumn('Outdegree_Closeness Centrality', format='%.12f')
            }
        )
        st.write("Indegree Closeness Centrality: Mean =", cc_in_mean, ", Std =", cc_in_std)
        st.write("Outdegree Closeness Centrality: Mean =", cc_out_mean, ", Std =", cc_out_std)

    with c4:
        st.dataframe(
            df_ev,
            column_config={
                'Indegree_Eigenvector Centrality': st.column_config.NumberColumn('Indegree_Eigenvector Centrality', format='%.12f'),
                'Outdegree_Eigenvector Centrality': st.column_config.NumberColumn('Outdegree_Eigenvector Centrality', format='%.12f')
            }
        )
        st.write("Indegree Eigenvector Centrality: Mean =", ev_in_mean, ", Std =", ev_in_std)
        st.write("Outdegree Eigenvector Centrality: Mean =", ev_out_mean, ", Std =", ev_out_std)

    kind = "Weighted" if weighted else "Binary"
    with c5:
        st.dataframe(
            df_hi,
            column_config={
                'HITS Hubs': st.column_config.NumberColumn('HITS Hubs', format='%.12f'),
                'HITS Authorities': st.column_config.NumberColumn('HITS Authorities', format='%.12f')
            }
        )
        st.write("HITS Hubs: Mean =", hub_mean, ", Std =", hub_std)
        st.write("HITS Authorities: Mean =", ah_mean, ", Std =", ah_std)
        _render_quadrant_scatter(
            df_hi, 'HITS Hubs', 'HITS Authorities',
            f'Hub & Authority Analysis ({kind})',
            key=f'{key_prefix}_hub_authority',
        )

    with c6:
        st.dataframe(
            df_kim,
            column_config={
                'Constraint factor': st.column_config.NumberColumn('Constraint factor', format='%.12f'),
                'Efficiency factor': st.column_config.NumberColumn('Efficiency factor', format='%.12f')
            }
        )
        st.write("Constraint factor: Mean =", const_mean, ", Std =", const_std)
        st.write("Efficiency factor: Mean =", eff_mean, ", Std =", eff_std)
        _render_quadrant_scatter(
            df_kim, 'Constraint', 'Efficiency',
            f'Structural Hole Analysis ({kind})',
            key=f'{key_prefix}_constraint_efficiency',
        )


### Streamlit 구현
def main():
    st.sidebar.header("데이터")
    render_japan_data_sidebar()
    st.sidebar.header("다운로드")
    st.title("산업연관데이터 DashBoard")
    mode = st.radio('모드 선택', preprocessing.MODES)
    params = preprocessing.get_mode_params(mode)
    first_idx = params.first_idx
    subplus_edit = params.subplus_edit
    number_of_label = params.number_of_label

    # US 모드는 연도 선택을 따로 받음 — 총거래/국산 워크북의 공통 연도 시트 목록 노출.
    us_year = None
    if mode.startswith("US"):
        avail_years = preprocessing.available_us_years(mode)
        cfg = preprocessing.get_us_config(mode)
        total_filename = cfg["total_filename"]
        local_filename = cfg["local_filename"]
        if not avail_years:
            st.error(
                f"`{mode}` 모드 데이터를 찾지 못했습니다. 저장소 루트에 "
                f"`{total_filename}` 와 `{local_filename}` 파일이 있어야 합니다."
            )
        else:
            us_year = st.selectbox(
                f"연도 선택  (가용: {avail_years[0]} ~ {avail_years[-1]}, 총 {len(avail_years)}개)",
                options=avail_years,
                index=len(avail_years) - 1,
            )
            level = cfg.get("level", "Summary")
            n_ind = 15 if level == "Sector" else 71
            st.caption(
                f"📂 총거래표: `{total_filename}`, 국산거래표: `{local_filename}` "
                f"(BEA Use {level} 기초가격 {n_ind}부문, 국산 = Use − 수입행렬). "
                f"Used→부가가치계 편입, Other→기타투입 행으로 분리(교수님 지침). "
                f"한국 모드와 동일한 파이프라인, 분모는 총산출(T018)."
            )

    if 'number_of_divide' not in st.session_state:
        st.session_state['number_of_divide'] = 0

    if "ids_simbol" not in st.session_state:
        st.session_state.ids_simbol = {}

    if "show_edited" not in st.session_state:
        st.session_state.show_edited = False
    if "edit_ops" not in st.session_state:
        st.session_state["edit_ops"] = [] 

    def _k(x):
        # 숫자 코드와 문자 코드가 섞여 있어도 정렬이 깨지지 않게 튜플 키 사용
        return (0, int(x), "") if x.isdigit() else (1, 0, x)

    # 파일 업로드 섹션
    st.session_state['uploaded_file'] = st.file_uploader("여기에 파일을 드래그하거나 클릭하여 업로드하세요.", type=['xls', 'xlsx'])

    # US 모드는 두 워크북이 저장소에 이미 있으므로, 업로드가 없으면 자동으로 사용.
    # (직접 워크북을 올리면 총거래표만 업로드본으로 대체되고 국산거래표는 저장소 파일 유지)
    load_source = st.session_state['uploaded_file']
    source_name = getattr(load_source, 'name', None)
    if load_source is None and mode.startswith("US") and us_year is not None:
        repo_use = preprocessing.us_use_file_path(mode)
        if repo_use is not None and repo_use.exists():
            load_source = str(repo_use)
            source_name = repo_use.name
            st.info(f"업로드 없이 저장소의 `{source_name}` (총거래) + 국산거래표를 자동 사용합니다.")
    st.session_state['uploaded_source_name'] = source_name

    # 모드/연도/파일이 바뀌면 이전에 로드·편집한 파이프라인을 전부 비워 새로 로드.
    # (안 그러면 모드를 바꿔도 직전 파일의 df 가 그대로 남아 "각 모드가 각각" 안 돌아감)
    load_sig = (mode, us_year, source_name)
    if st.session_state.get('_load_sig') != load_sig:
        # 데이터/행렬 계열은 완전히 제거 (없으면 아래 로드 게이트가 새로 채움)
        for _k_reset in [
            'df', 'df_local', 'mid_ID_idx', 'mid_ID_idx_local',
            'df_editing', 'df_editing_local',
            'df_edited', 'df_edited_local',
            'alpha_key', 'batch_df_clean', 'batch_meta', 'batch_preview_lines',
            'threshold', 'threshold_cal', 'remove_positions',
        ]:
            st.session_state.pop(_k_reset, None)
        # 하단에서 무조건 참조되는 카운터/로그는 기본값으로 재설정 (pop 하면 KeyError)
        st.session_state['edit_ops'] = []
        st.session_state['ids_simbol'] = {}
        st.session_state['number_of_divide'] = 0
        st.session_state['show_edited'] = False
        st.session_state['data_editing_log'] = ''
        st.session_state['_load_sig'] = load_sig

    if 'df' not in st.session_state and load_source is not None:
        st.write(source_name)
        result = preprocessing.load_workbook(
            load_source, mode, us_year=us_year,
        )
        st.session_state['df']               = result.df
        st.session_state['df_local']         = result.df_local
        st.session_state['mid_ID_idx']       = result.mid_ID_idx
        st.session_state['mid_ID_idx_local'] = result.mid_ID_idx_local
        st.write(result.string_values)
        st.write(result.string_values_local)

    if 'df' in st.session_state:
        uploaded_matrix_X = get_submatrix_withlabel(st.session_state['df'], first_idx[0], first_idx[1], st.session_state['mid_ID_idx'][0], st.session_state['mid_ID_idx'][1], first_idx, numberoflabel=number_of_label)
        uploaded_matrix_R = get_submatrix_withlabel(st.session_state['df'], st.session_state['mid_ID_idx'][0]+1, first_idx[1], st.session_state['df'].shape[0]-1, st.session_state['mid_ID_idx'][1], first_idx, numberoflabel=number_of_label)
        uploaded_matrix_C = get_submatrix_withlabel(st.session_state['df'], first_idx[0], st.session_state['mid_ID_idx'][1]+1, st.session_state['mid_ID_idx'][0], st.session_state['df'].shape[1]-1, first_idx, numberoflabel=number_of_label)

        uploaed_files = {
        "uploaded_df": st.session_state['df'],
        "uploaded_matrix_X": uploaded_matrix_X,
        "uploaded_matrix_R": uploaded_matrix_R,
        "uploaded_matrix_C": uploaded_matrix_C
                                }
        with st.sidebar.expander("최초 업로드 원본 파일"):
            download_multiple_csvs_as_zip(uploaed_files, zip_name="최초 업로드 원본 파일 전체(zip)")
            donwload_data(st.session_state['df'], 'uploaded_df')
            donwload_data(uploaded_matrix_X, 'uploaded_matrix_X')
            donwload_data(uploaded_matrix_R, 'uploaded_matrix_R')
            donwload_data(uploaded_matrix_C, 'uploaded_matrix_C')
        # 원본 부분 header 표시
        st.header('최초 업로드 된 Excel파일 입니다.')
        # 데이터프레임 표시 
        tab1, tab2, tab3, tab4 = st.tabs(['uploaded_df', 'uploaded_matrix_X', 'uploaded_matrix_R', 'uploaded_matrix_C'])
        with tab1:
            st.write(st.session_state['df'])
        with tab2:
            st.write(uploaded_matrix_X)
        with tab3:
            st.write(uploaded_matrix_R)
        with tab4:
            st.write(uploaded_matrix_C)

        if 'df_editing' not in st.session_state:
            st.session_state['df_editing'] = st.session_state['df'].copy()
            st.session_state['df_editing_local'] = st.session_state['df_local'].copy()
            col = first_idx[1] - number_of_label                 # 라벨 열 위치
            s   = st.session_state['df_editing'].iloc[:, col]    # 해당 열 Series

            # ── ① float64 → Int64(정수, NaN 허용) ─────────────────────────────
            if pd.api.types.is_float_dtype(s):
                s = s.astype('Int64')        # 1.0 → 1,  NaN 그대로 유지
                s = s.astype('string')        # 1.0 → 1,  NaN 그대로 유지
                st.session_state['df_editing'].iloc[:, col] = s.astype('object') 
                st.session_state['df_editing_local'].iloc[:, col] = s.astype('object') 

    if 'data_editing_log' not in st.session_state:
        st.session_state['data_editing_log'] = ''

    if 'df_editing' in st.session_state:
        st.header("DataFrame을 수정합니다.")
        st.markdown("#### 자동 입력 처리 (엑셀 파일로 일괄 처리)")
        
        # =========================
        # Batch Processing (업로드 즉시 준비 -> 텍스트 미리보기 -> 적용 버튼)
        # =========================
        alpha_file = st.file_uploader("Alpha 값 엑셀/ZIP 파일 업로드", type=["xlsx", "xls", "zip"])

        if alpha_file:
            # 원본 업로드 파일명(확장자 제외) - ZIP 매칭에만 사용
            # US 자동로드 시 uploaded_file 이 None 이므로 저장해 둔 소스명을 사용
            _src_name = st.session_state.get("uploaded_source_name") or getattr(
                st.session_state.get("uploaded_file"), "name", ""
            ) or ""
            original_filename_no_ext = _src_name.rsplit(".", 1)[0]

            # 업로드 파일 변경 감지 (rerun에서도 중복 준비 방지)
            alpha_key = (alpha_file.name, len(alpha_file.getvalue()))
            if st.session_state.get("alpha_key") != alpha_key:
                st.session_state["alpha_key"] = alpha_key

                # 업로드 즉시 1단계+2단계 자동 수행
                try:
                    batch_df_clean, meta, preview_lines, summary_lines = prepare_batch_preview(
                        alpha_file, original_filename_no_ext
                    )
                    st.session_state["batch_df_clean"] = batch_df_clean
                    st.session_state["batch_meta"] = meta
                    st.session_state["batch_preview_lines"] = preview_lines
                except Exception as e:
                    st.session_state["batch_df_clean"] = None
                    st.error(f"미리보기 준비 중 오류: {e}")

            # --- 2단계: 텍스트 미리보기 출력 ---
            if st.session_state.get("batch_df_clean") is not None:
                st.markdown("##### 일괄 적용 내역 요약")
                df_prev = st.session_state["batch_df_clean"].copy()
                df_prev["from"] = df_prev["from"].astype(str)
                df_prev["to"]   = df_prev["to"].astype(str)
                df_prev["to_name"] = df_prev["to_name"].astype(str).replace("nan", "").fillna("")

                # to -> from 순 정렬 ( _k는 위에서 정의/이동된 함수 사용 )
                df_prev = df_prev.sort_values(by=["to", "from"], key=lambda s: s.map(_k))

                # to별 그룹 출력 (그룹키는 to 코드로 유지)
                for idx, (to_code, g) in enumerate(df_prev.groupby("to", sort=False), start=1):
                    # ✅ 표시용 이름: 그룹 내 to_name 고유값
                    names = [n for n in g["to_name"].dropna().unique().tolist() if n and n != "None"]
                    if len(names) == 0:
                        display_name = to_code
                    elif len(names) == 1:
                        display_name = names[0]
                    else:
                        display_name = f"{names[0]} 외 {len(names)-1}"

                    st.markdown(f"**[{idx}: {display_name}]**")

                    lines = [
                        f"{r['from']} -> {r['to']} : {float(r['alpha'])*100:.4f}%"
                        for _, r in g.iterrows()
                    ]
                    for i in range(0, len(lines), 5):
                        st.write(" | ".join(lines[i:i+5]))


                # --- 3단계: 적용 버튼 누르면 실제 업데이트 실행 ---
                if st.button("일괄 적용"):
                    try:
                        batch_df = st.session_state["batch_df_clean"]

                        df_new, mid_new, ids_new, log_msg = apply_batch_edit(
                            batch_df=batch_df,
                            df_curr=st.session_state["df_editing"],
                            first_idx=first_idx,
                            number_of_label=number_of_label,
                            mid_ID_idx=st.session_state["mid_ID_idx"],
                            ids_simbol=st.session_state.ids_simbol,
                            insert_row_and_col_fn = insert_row_and_col,
                        )

                        st.session_state["df_editing"] = df_new
                        st.session_state["mid_ID_idx"] = mid_new
                        st.session_state.ids_simbol = ids_new

                        # 바깥에서 로그 누적
                        st.session_state["data_editing_log"] += (log_msg + "\n\n")

                        # ops 엔진 기록
                        st.session_state["edit_ops"].append({
                             "type": "batch_apply",
                             "batch_records": batch_df.to_dict("records")
                         })

                        st.session_state.show_edited = False
                        st.rerun()

                    except Exception as e:
                        st.error(f"처리 중 오류 발생: {e}")

        # Manual Processing (Existing)
        st.markdown("#### 수동 입력")
        col1, col2, col3 = st.columns(3)
        with col1:
            new_code = st.text_input('새로 삽입할 산업의 code를 입력하세요')
        with col2:
            name = st.text_input('새로 삽입할 산업의 이름을 입력하세요')
        with col3:
            if st.button('산업 추가'):
                result = insert_row_and_col(st.session_state['df_editing'], first_idx, st.session_state['mid_ID_idx'], new_code, name, number_of_label)
                st.session_state['df_editing'], st.session_state['mid_ID_idx'] = result[0:2]
                st.session_state['data_editing_log'] += (result[2] + '\n\n')
                if new_code not in st.session_state.ids_simbol:
                    st.session_state.ids_simbol[new_code] = []  # 새로운 리스트 생성
                st.session_state.ids_simbol[new_code].append(name)  # 값 추가
                st.session_state.show_edited = False

                st.session_state["edit_ops"].append({
                "type": "insert_sector",
                "code": str(new_code),
                "name": str(name),
                })

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            origin_code = st.text_input('from')
        with col2:
            target_code = st.text_input('to')
        with col3:
            alpha = float(st.text_input('alpha value (0.000 to 1.000)', '0.000'))
        with col4:
            if st.button('값 옮기기'):
                result = transfer_to_new_sector(st.session_state['df_editing'], first_idx, origin_code, target_code, alpha)
                st.session_state['df_editing'] = result[0]
                st.session_state['data_editing_log'] += (result[1] + '\n\n')

                st.session_state["edit_ops"].append({
                    "type": "transfer",
                    "from": str(origin_code),
                    "to": str(target_code),
                    "alpha": float(alpha),
                })
                st.session_state.show_edited = False
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button('0인 행(열) 삭제'):
                df_editing_t, msg_t, mid_ID_idx_t, removed_positions_t = remove_zero_series(
                    st.session_state['df_editing'],
                    first_idx,
                    st.session_state['mid_ID_idx']
                )

                st.session_state['df_editing'] = df_editing_t
                st.session_state['data_editing_log'] += (msg_t + '\n\n')
                st.session_state['mid_ID_idx'] = mid_ID_idx_t
                st.session_state['remove_positions'] = removed_positions_t


                st.session_state["edit_ops"].append({"type": "remove_zero", "remove_positions": st.session_state['remove_positions']})
                st.session_state.show_edited = False
        with col2:
             if st.button('-값 절반으로 줄이기'):
                mid_ID_idx_reduced = (st.session_state['mid_ID_idx'][0] - 1, st.session_state['mid_ID_idx'][1] - 1)
                result = reduce_negative_values(st.session_state['df_editing'], first_idx, mid_ID_idx_reduced)
                st.session_state['df_editing'] = result[0]
                st.session_state['data_editing_log'] += (result[1] + '\n\n')
                st.session_state['number_of_divide'] +=1

                st.session_state["edit_ops"].append({"type": "reduce_negative", "use_minus_one_mid": True})
                st.session_state.show_edited = False
        with col3:
            if st.button('전체 적용'):
                st.session_state['df_edited'] = st.session_state['df_editing'].copy()
                st.session_state.show_edited = True
                
                if "df_local" in st.session_state:
                    df_local_new, mid_local_new, ids_local_new = replay_edit_ops_on_df(
                        df_base=st.session_state["df_editing_local"],
                        mid_ID_idx_base=st.session_state["mid_ID_idx_local"],
                        ids_simbol_base=st.session_state.ids_simbol,   # 공유 싫으면 local dict 따로 두기
                        ops=st.session_state["edit_ops"],
                        first_idx=first_idx,
                        number_of_label=number_of_label,
                        insert_row_and_col_fn=insert_row_and_col,
                        transfer_to_new_sector_fn=transfer_to_new_sector,
                        remove_zero_series_fn=remove_zero_series,
                        reduce_negative_values_fn=reduce_negative_values,
                        return_log=False,
                        batch_apply_fn=apply_batch_edit
                    )
                    st.session_state["df_editing_local"] = df_local_new
                    st.session_state["mid_ID_idx_local"] = mid_local_new

                    st.session_state["df_edited_local"] = st.session_state['df_editing_local'].copy()

                # 3) ✅ pending ops 비우기(중복 적용 방지)
                st.session_state["edit_ops"] = []
        st.markdown(f"##### - 값 나누는 것: **{st.session_state['number_of_divide']}** 번 적용")
        st.write(st.session_state['df_editing'])

    if 'df_edited' in st.session_state and st.session_state.show_edited:
        st.header('위에서 수정 된 Excel파일 입니다.')
        edited_matrix_X = get_submatrix_withlabel(st.session_state['df_edited'], first_idx[0],first_idx[1], st.session_state['mid_ID_idx'][0], st.session_state['mid_ID_idx'][1], first_idx, numberoflabel = 2)
        edited_matrix_X_local = get_submatrix_withlabel(st.session_state['df_edited_local'], first_idx[0],first_idx[1], st.session_state['mid_ID_idx_local'][0], st.session_state['mid_ID_idx_local'][1], first_idx, numberoflabel = 2)
        edited_matrix_R = get_submatrix_withlabel(st.session_state['df_edited'], st.session_state['mid_ID_idx'][0]+1,first_idx[1], st.session_state['df_edited'].shape[0]-1, st.session_state['mid_ID_idx'][1], first_idx, numberoflabel = 2)
        edited_matrix_C = get_submatrix_withlabel(st.session_state['df_edited'], first_idx[0], st.session_state['mid_ID_idx'][1]+1, st.session_state['mid_ID_idx'][0], st.session_state['df_edited'].shape[1]-1, first_idx, numberoflabel = 2)

        edited_files = {
        "edited_df": st.session_state['df_edited'],
        "edited_matrix_X": edited_matrix_X,
        "edited_matrix_R": edited_matrix_R,
        "edited_matrix_C": edited_matrix_C
                                }
        with st.sidebar.expander("수정된 파일"):
            download_multiple_csvs_as_zip(edited_files, zip_name="수정된 파일 전체(zip)")
            donwload_data(st.session_state['df_edited'], 'edited_df')
            donwload_data(edited_matrix_X, 'edited_matrix_X')
            donwload_data(edited_matrix_R, 'edited_matrix_R')
            donwload_data(edited_matrix_C, 'ueditedmatrix_C')
        # 데이터프레임 표시
        tab1, tab2, tab3, tab4 = st.tabs(['edited_df', 'edited_matrix_X', 'edited_matrix_R', 'edited_matrix_C'])

        with tab1:
            st.write(st.session_state['df_edited'])

        with tab2:
            st.write(edited_matrix_X)

        with tab3:
            st.write(edited_matrix_R)

        with tab4:
            st.write(edited_matrix_C)

    if 'df_edited' in st.session_state and st.session_state.show_edited:
        st.session_state['df_for_leontief'] = edited_matrix_X.iloc[:-1, :-1].copy()
        st.session_state['df_for_leontief'].index = range(st.session_state['df_for_leontief'].shape[0])
        st.session_state['df_for_leontief'].columns = range(st.session_state['df_for_leontief'].shape[1])

        st.session_state['df_for_leontief_local'] = edited_matrix_X_local.iloc[:-1, :-1].copy()
        st.session_state['df_for_leontief_local'].index = range(st.session_state['df_for_leontief_local'].shape[0])
        st.session_state['df_for_leontief_local'].columns = range(st.session_state['df_for_leontief_local'].shape[1])

        st.session_state['df_for_r'] = edited_matrix_R.iloc[:-1, :-1].copy()
        st.session_state['df_for_r'].index = range(st.session_state['df_for_r'].shape[0])
        st.session_state['df_for_r'].columns = range(st.session_state['df_for_r'].shape[1])

        st.session_state['normalization_denominator'] = st.session_state['df_edited'].iloc[st.session_state['df_edited'].shape[0]-1, first_idx[1]:st.session_state['mid_ID_idx'][1]]
        st.session_state['normalization_denominator'] = pd.to_numeric(st.session_state['normalization_denominator'])
        st.session_state['normalization_denominator_replaced'] = st.session_state['normalization_denominator'].replace(0, np.finfo(float).eps)

        
        st.session_state['added_value_denominator'] = st.session_state['df_edited'].iloc[st.session_state['df_edited'].shape[0] - 2, first_idx[1]:st.session_state['mid_ID_idx'][1]]
        st.session_state['added_value_denominator'] = pd.to_numeric(st.session_state['added_value_denominator'])
        st.session_state['added_value_denominator_replaced'] = st.session_state['added_value_denominator'].replace(0, np.finfo(float).eps)

        # 2025-12-26 추가
        st.session_state['v'] = (st.session_state['added_value_denominator'] / st.session_state['normalization_denominator_replaced'])

        v_vec = st.session_state['v'].to_numpy()
        V_matrix = np.diag(v_vec)
        st.session_state['V'] = V_matrix

        # 1) 두번째 행(= iloc[1])에서 '최종수요계' 찾기
        tmp_header_C = edited_matrix_C.iloc[1].fillna("").astype(str).str.strip()

        # 정확히 일치로 찾기
        pos = np.where(tmp_header_C.values == "최종수요계")[0]
        if len(pos) == 0:
            # 혹시 공백/표기가 다른 경우 대비(부분일치)
            pos = np.where(tmp_header_C.str.contains("최종수요", na=False).values)[0]

        if len(pos) == 0:
            raise ValueError("edited_matrix_C의 2번째 행에서 '최종수요계' 열을 못 찾았음")

        col_pos = int(pos[0])  # '최종수요계' 열의 '위치(정수)'

        # edited_matrix_C 산업 행은 iloc[2:]부터 시작(라벨 2행 제거)
        st.session_state['y'] = pd.to_numeric(edited_matrix_C.iloc[2:, col_pos], errors="coerce").to_numpy().reshape(-1, 1)






        
    if 'df_for_leontief' in st.session_state and st.session_state.show_edited:
        st.session_state["df_for_local_leontief_with_label"] , st.session_state["df_for_local_leontief_without_label"]= build_leontief_outputs(
        st.session_state["df_for_leontief_local"],
        st.session_state["normalization_denominator_replaced"],
    ) # for local 

        st.session_state['df_for_leontief_with_label'] = st.session_state['df_for_leontief'].copy()
        st.session_state['df_for_leontief_without_label'] = st.session_state['df_for_leontief_with_label'].iloc[2:, 2:].copy()
        st.session_state['df_for_r_without_label'] = st.session_state['df_for_r'].iloc[2:, 2:].copy()
        st.session_state['df_for_r_with_label'] = st.session_state['df_for_r'].copy()
        
        tmp = st.session_state['df_for_leontief_without_label'].copy()
        tmp = tmp.apply(pd.to_numeric, errors='coerce')
        tmp = tmp.divide(st.session_state['normalization_denominator_replaced'], axis=1) ##d

        tmp2 = st.session_state['df_for_r_without_label'].copy()
        tmp2 = tmp2.apply(pd.to_numeric, errors='coerce')
        tmp2 = tmp2.divide(st.session_state['normalization_denominator_replaced'], axis=1) ##d
    
        st.session_state['df_for_leontief_with_label'].iloc[2:, 2:] = tmp
        st.session_state['df_for_r_with_label'].iloc[2:, 2:] = tmp2

        st.session_state['df_normalized_with_label'] = st.session_state['df_for_leontief_with_label'].copy()
        unit_matrix = np.eye(tmp.shape[0])
        subtracted_matrix = unit_matrix - tmp
        leontief = np.linalg.inv(subtracted_matrix.values)
        leontief = pd.DataFrame(leontief)
        # 현재 DataFrame을 가져오기
        current_df = st.session_state['df_for_leontief_with_label']

        # 기존 DataFrame에서 2행과 2열을 제거한 후, 크기를 정의
        existing_rows = current_df.shape[0] - 2  # 기존 DataFrame의 행 수
        existing_cols = current_df.shape[1] - 2  # 기존 DataFrame의 열 수

        # leontief 배열의 크기
        leontief_rows, leontief_cols = leontief.shape

        # 새로운 DataFrame 생성 (NaN으로 초기화)
        new_df = pd.DataFrame(np.nan, index=range(existing_rows + 1), columns=range(existing_cols + 1))

        # leontief 배열이 기존 크기와 일치할 때
        if leontief_rows == existing_rows and leontief_cols == existing_cols:
            # leontief 데이터를 새로운 DataFrame의 적절한 부분에 삽입
            new_df.iloc[:existing_rows, :existing_cols] = leontief  # 기존 데이터 부분에 할당

        # N*N 배열에서 N+1*N+1로 변환
        leontief_with_sums = np.zeros((leontief_rows + 1, leontief_cols + 1))
        leontief_with_sums[:-1, :-1] = leontief  # 기존 leontief 배열을 넣기
        leontief_with_sums[-1, :-1] = leontief.sum(axis=0)  # 마지막 행에 각 열의 합
        leontief_with_sums[:-1, -1] = leontief.sum(axis=1)  # 마지막 열에 각 행의 합

        # 마지막 행 값들을 마지막 행 평균으로 나누기
        last_row_mean = leontief_with_sums[-1, :-1].mean()  # 마지막 행 평균
        leontief_with_sums[-1, :-1] /= last_row_mean  # 마지막 행 나누기

        # 마지막 열 값들을 마지막 열 평균으로 나누기
        last_col_mean = leontief_with_sums[:-1, -1].mean()  # 마지막 열 평균
        leontief_with_sums[:-1, -1] /= last_col_mean  # 마지막 열 나누기

        # 최종적으로 N+1*N+1 배열을 새로운 DataFrame에 업데이트
        # 새로운 크기로 DataFrame을 초기화합니다.
        new_df = pd.DataFrame(leontief_with_sums)
        # 기존 DataFrame의 크기를 1씩 늘리기 (NaN으로 초기화)
        current_df = current_df.reindex(index=range(existing_rows + 3), 
                                        columns=range(existing_cols + 3))


        # 새로운 DataFrame을 기존 DataFrame의 적절한 위치에 업데이트
        current_df.iloc[2:2 + new_df.shape[0], 2:2 + new_df.shape[1]] = new_df
        current_df.iloc[1,-1]="FL"
        current_df.iloc[-1,1]="BL"
        # 세션 상태에 업데이트
        st.session_state['df_for_leontief_with_label'] = current_df


        ids_col = st.session_state['df_for_leontief_with_label'].iloc[1:-1, :2]
        fl_data = st.session_state['df_for_leontief_with_label'].iloc[1:-1, -1]
        bl_data = st.session_state['df_for_leontief_with_label'].iloc[-1, 1:-1]
        
        # DataFrame으로 변환 (bl_data가 Series일 경우 df로 변환 필요)
        fl_data = fl_data.to_frame(name="2")  # FL 열 이름 지정
        bl_data = bl_data.to_frame(name="3")  # BL 열 이름 지정

        # 인덱스를 리셋하여 병합이 가능하도록 정리
        ids_col = ids_col.reset_index(drop=True)
        fl_data = fl_data.reset_index(drop=True)
        bl_data = bl_data.reset_index(drop=True)

        # 좌우로 데이터프레임 결합 (concat 사용)
        st.session_state['fl_bl'] = pd.concat([ids_col, fl_data, bl_data], axis=1)

        st.session_state['df_for_leontief_with_label']=st.session_state['df_for_leontief_with_label'].iloc[:-1, :-1]
        st.session_state['df_for_leontief_without_label'] = st.session_state['df_for_leontief_with_label'].iloc[2:, 2:].copy()

        # 2025-12-26 추가 (GDP 및 부가가치 유발 효과)
        # L, y, V 준비
        L = st.session_state['df_for_leontief_without_label'].apply(pd.to_numeric, errors='coerce').fillna(0).to_numpy()
        L_local = st.session_state['df_for_local_leontief_without_label'].apply(pd.to_numeric, errors='coerce').fillna(0).to_numpy()
        y = np.asarray(st.session_state['y']).reshape(-1, 1)
        y = y[:-1, :] 

        y_vec = y.reshape(-1)           # (n,) 1D로 만들기
        Y_matrix = np.diag(y_vec)       # (n,n) 대각행렬

        V = st.session_state['V']
        v = np.asarray(st.session_state['v'], dtype=float).reshape(1, -1)


        # GDP 생성
        x = L @ y
        g = V @ x

        # 부가가치 유발 효과
        m_v = v @ L_local

        # W 생성
        tmp_w = L @ Y_matrix
        W =  V @ tmp_w


        # =========================
        # g1,g2,g3 생성
        # =========================
        base_df = st.session_state["df_for_leontief_with_label"]
        ids_col = base_df.iloc[1:, :2].reset_index(drop=True)

        # 1) W 정리
        W = np.asarray(W, dtype=float)
        gn_n = W.shape[0]
        gn_ones = np.ones((gn_n, 1), dtype=float)

        # 2) g1,g2,g3
        g1_vec = (W @ gn_ones).reshape(-1)          # g1 = (W*1)^t  -> (n,)
        g2_vec = (gn_ones.T @ W).reshape(-1)        # g2 = 1^t*W    -> (n,)
        g3_vec = np.diag(W).reshape(-1)          # g3 = diag(W)  -> (n,)

        g123_vec = g1_vec + g2_vec - g3_vec      # (n,)

        g1_data   = make_col("g1", g1_vec, "2")
        g2_data   = make_col("g2",   g2_vec, "3")
        g3_data   = make_col("g3", g3_vec, "4")
        g123_data = make_col("g1+g2-g3",   g123_vec, "5")

        # 3) 최종 테이블
        st.session_state["g123_by_sector"] = pd.concat(
            [ids_col, g1_data, g2_data, g3_data, g123_data],
            axis=1
        )

        # 4) 요약값
        st.session_state["g1_total"],   st.session_state["g1_mean"]   = float(g1_vec.sum()),   float(g1_vec.mean())
        st.session_state["g2_total"],   st.session_state["g2_mean"]   = float(g2_vec.sum()),   float(g2_vec.mean())
        st.session_state["g3_total"],   st.session_state["g3_mean"]   = float(g3_vec.sum()),   float(g3_vec.mean())
        st.session_state["g123_total"], st.session_state["g123_mean"] = float(g123_vec.sum()), float(g123_vec.mean())

        # =========================
        # GDP(산업별 VA 유발액)
        # =========================
        g_vec = np.asarray(g, dtype=float).reshape(-1)
        g_col = make_col("GDP", g_vec, colname="2")

        st.session_state["gdp_by_industry"] = make_table(base_df, [g_col])
        st.session_state["GDP_total"] = float(g_vec.sum())
        st.session_state["GDP_mean"]  = float(g_vec.mean())

        # =========================
        # 부가가치 유발효과(m_v)
        # =========================
        mv_vec = np.asarray(m_v, dtype=float).reshape(-1)
        mv_col = make_col("부가가치유발효과", mv_vec, colname="2")

        st.session_state["va_multiplier_by_sector"] = make_table(base_df, [mv_col])
        st.session_state["m_v_total"] = float(mv_vec.sum())
        st.session_state["m_v_mean"]  = float(mv_vec.mean())







        st.subheader('Leontief 과정 matrices')
        col1, col2, col3, col4, col5, col6, col7, col8, col9, col10= st.tabs(['edited_df', 'normailization denominator', '투입계수행렬', 'leontief inverse','FL-BL','g_series', 'GDP','부가가치유발효과(국내)','부가가치계수행렬','부가가치계벡터'])
        with col1:
            st.write(st.session_state['df_for_leontief'])
        with col2:
            st.write(st.session_state['normalization_denominator'])
        with col3:
            st.write(st.session_state['df_normalized_with_label'])
        with col4:
            st.write(st.session_state['df_for_leontief_with_label'])
            invalid_positions = []
        with col5:
            st.write(st.session_state['fl_bl'])

        with col6:
            st.write(st.session_state["g123_by_sector"])
            # 화면을 2구역(좌: totals / 우: means)으로 분할
            col_total, col_mean = st.columns(2)

            with col_total:
                st.write("##### Totals")
                st.write("g1_total:" ,st.session_state['g1_total'])
                st.write("g2_total:" ,st.session_state['g2_total'])
                st.write("g3_total:" ,st.session_state['g3_total'])
                st.write("g1+g2-g3_total:", st.session_state['g123_total'])

            with col_mean:
                st.write("##### Means")
                st.write("g1_mean:", st.session_state['g1_mean'])
                st.write("g2_mean:", st.session_state['g2_mean'])
                st.write("g3_mean:", st.session_state['g3_mean'])
                st.write("g1+g2-g3_mean:" ,st.session_state['g123_mean'])

        with col7:
            st.write(st.session_state['gdp_by_industry'])
            st.write("GDP_total (sum g):", st.session_state['GDP_total'])
            st.write("GDP_mean (mean g):", st.session_state['GDP_mean'])
        with col8:
            st.write(st.session_state['va_multiplier_by_sector'])
            st.write("m_v_total (sum m_v):", st.session_state['m_v_total'])
            st.write("m_v_mean (mean m_v):", st.session_state['m_v_mean'])
        with col9:
            st.write(st.session_state['df_for_r_with_label'])
        with col10:
            st.write(st.session_state['added_value_denominator'])

        st.subheader("레온티에프 역행렬을 통한 정합성 검증 내용")
        is_equal_to_one_row = np.isclose(leontief_with_sums[-1, :-1].mean(), 1)
        st.write(f"행(영향력계수) 합의 평균이 1과 동일 여부 {is_equal_to_one_row}")
        is_equal_to_one_row = np.isclose(leontief_with_sums[:-1, -1].mean(), 1)
        st.write(f"열(감응도계수) 합의 평균이 1과 동일 여부 {is_equal_to_one_row}")


        # 1. 행렬을 순회하며 -0.1 ~ 2 범위를 벗어난 값의 위치를 찾음
        for i in range(leontief.shape[0]):
            for j in range(leontief.shape[1]):
                value = leontief.iloc[i, j]
                if not (-0.1 <= value <= 2):
                    invalid_positions.append((i + 2, j + 2, value))  # 위치 조정 (+2)

        # 2. 대각 원소 중 1 이하인 값의 위치와 값 저장
        diagonal_invalid_positions = []
        for i in range(leontief.shape[0]):
            value = leontief.iloc[i, i]
            if value < 1:
                diagonal_invalid_positions.append((i + 2, i + 2, value))  # 위치 조정 (+2)

        # 결과 출력 (위반이 수천 개면 페이지가 멈추므로 상위 200개만 표시)
        _max_show = 200
        if invalid_positions:
            st.write(f"조건(-0.1 ~ 2.0)에 맞지 않는 위치와 값: 총 {len(invalid_positions)}개")
            for pos in invalid_positions[:_max_show]:
                st.write(f"위치: {pos[:2]}, 값: {pos[2]}")
            if len(invalid_positions) > _max_show:
                st.write(f"... 외 {len(invalid_positions) - _max_show}개 (상위 {_max_show}개만 표시)")
        else:
            st.write("모든 값이 -0.1 ~ 2 사이의 조건을 만족합니다.")

        # 대각 원소 조건 확인 및 결과 출력
        if diagonal_invalid_positions:
            st.write(f"대각 원소 중 1 미만인 값이 있습니다: 총 {len(diagonal_invalid_positions)}개")
            for pos in diagonal_invalid_positions[:_max_show]:
                st.write(f"위치: {pos[:2]}, 값: {pos[2]}")
            if len(diagonal_invalid_positions) > _max_show:
                st.write(f"... 외 {len(diagonal_invalid_positions) - _max_show}개 (상위 {_max_show}개만 표시)")
        else:
            st.write("모든 대각 원소가 1보다 큽니다.")



        with st.sidebar.expander('Leontief 과정 matrices'):
            leontief_files = {
            "normalization_denominator": st.session_state['normalization_denominator'],
            "투입계수행렬": st.session_state['df_normalized_with_label'],
            "leontief inverse": st.session_state['df_for_leontief_with_label'],
            "FL-BL": st.session_state['fl_bl'],
            "GDP": st.session_state['gdp_by_industry'],
            "부가가치유발효과": st.session_state['va_multiplier_by_sector'],
            "부가가치계수행렬": st.session_state['df_for_r_with_label'],
            "부가가치계벡터": st.session_state['added_value_denominator']
            }
            download_multiple_csvs_as_zip(leontief_files, zip_name="Leontief 과정 전체(zip)")
            donwload_data(st.session_state['normalization_denominator'], 'normailization denominator')
            donwload_data(st.session_state['df_normalized_with_label'], '투입계수행렬')
            donwload_data(st.session_state['df_for_leontief_with_label'], 'leontief inverse')
            donwload_data(st.session_state['fl_bl'], 'FL-BL')
            donwload_data(st.session_state['gdp_by_industry'], 'GDP')
            donwload_data(st.session_state['va_multiplier_by_sector'], '부가가치유발효과')
            donwload_data(st.session_state['df_for_r_with_label'], '부가가치계수행렬')
            donwload_data(st.session_state['added_value_denominator'], '부가가치계벡터')


        st.subheader("FL-BL Plot")

        # -----------------------------
        # 1) ids_values 만들기 + (중복 제거, 순서 유지)
        # -----------------------------
        ids_values = [item for sublist in st.session_state.ids_simbol.values() for item in sublist]

        seen = set()
        ids_unique = []
        for x in ids_values:
            if x not in seen:
                seen.add(x)
                ids_unique.append(x)

        # -----------------------------
        # 2) 토글을 "한 행"에 전부 배치 (각 아이템별 토글)
        #    - 기본값 True (전부 ON)
        # -----------------------------
        if len(ids_unique) > 0:
            cols = st.columns(len(ids_unique))  # ✅ 한 줄에 전부
            selected_ids = []
            for i, name in enumerate(ids_unique):
                # key는 안전하게(특수문자 제거) + i 붙여서 중복 방지
                safe = re.sub(r"[^0-9a-zA-Z가-힣_]", "_", str(name))
                key = f"hl_{i}_{safe}"

                with cols[i]:
                    if st.toggle(str(name), value=True, key=key):
                        selected_ids.append(name)
        else:
            selected_ids = []

        # -----------------------------
        # 3) DF 준비 (첫 행 제거는 통일)
        # -----------------------------
        df = st.session_state['fl_bl'].copy()
        df = df.iloc[1:, :]

        highlight_df = df[df[1].isin(selected_ids)]

        # -----------------------------
        # 4) Plot: 전체는 other 스타일로 그리고,
        #         토글 ON인 애들만 빨간 + 라벨 overlay
        # -----------------------------
        fig, ax = plt.subplots(figsize=(12, 10))

        # 전체 기본 점 (other 스타일)
        ax.scatter(df['2'], df['3'], facecolors='none', edgecolors='black', s=100)

        # 선택된 애들만 강조 + 라벨
        if not highlight_df.empty:
            ax.scatter(highlight_df['2'], highlight_df['3'], color='red', s=150)
            for _, row in highlight_df.iterrows():
                ax.text(row['2'], row['3'], row[1], color='black', fontsize=16, ha='right')

        ax.set_xlabel('FL', fontsize=14)
        ax.set_ylabel('BL', fontsize=14)
        ax.axhline(1, color='black', linestyle='--', linewidth=1)
        ax.axvline(1, color='black', linestyle='--', linewidth=1)

        st.pyplot(fig)


        # 사이드바 expander 에 다운로드 버튼 추가
        with st.sidebar.expander("Plot 다운로드"):
            buf = io.BytesIO()
            # PNG 포맷으로 버퍼에 저장
            fig.savefig(buf, format="png", bbox_inches="tight")
            buf.seek(0)
            st.download_button(
                label="Plot 이미지 다운로드",
                data=buf,
                file_name="fl_bl_plot.png",
                mime="image/png"
            )

        win_A = st.session_state['df_normalized_with_label'].iloc[2:, 2:].copy().values
        win_epsilon = 0.05

        win_N0 = compute_leontief_inverse(win_A, epsilon=win_epsilon)

        win_Diagon, win_N = separate_diagonals(win_N0)

        st.markdown("---")

        # --------------------------------------------------------------------------------
        # [Step 1] 초기화 함수 정의
        # 라디오 버튼(메소드)이 변경될 때 호출되어, 하단 결과창의 상태(state)를 지워버립니다.
        # --------------------------------------------------------------------------------
        def reset_threshold_state():
            # '2. filtering 결과' 섹션을 제어하는 핵심 변수들 삭제
            keys_to_remove = ['threshold', 'threshold_cal']
            for key in keys_to_remove:
                if key in st.session_state:
                    del st.session_state[key]



        # ---------------------------------------------------------------------
        # 2. [UI] 라디오 버튼으로 방식 선택 (즉시 전환)
        # ---------------------------------------------------------------------
        st.header("2. 네트워크 추출")
        
        # 1) Method A 분석 미리보기 (항상 표시 / Expander)
        with st.expander("Method A 분석 결과 (Threshold Optimization)", expanded=False):
             if 'df_for_leontief_with_label' in st.session_state:
                 # threshold_count 내부에서 그래프 및 텍스트 출력
                 threshold_count(st.session_state['df_for_leontief_with_label'].iloc[2:, 2:])

        # 2) Method B 파라미터 설정
        st.markdown("##### Method B 파라미터 설정")
        col_eps, col_del, col_maxiter = st.columns(3)
        with col_eps:
            mb_epsilon = st.number_input('ε (epsilon)', value=1e-4, format='%.6f', step=1e-5,
                                         help='B^t 원소 중 이 값 이하인 것을 0으로 제거합니다.')
        with col_del:
            mb_delta = st.number_input('δ (delta)', value=0.01, format='%.4f', step=0.001,
                                       help='Change Ratio r이 이 값 미만이면 수렴으로 판단합니다.')
        with col_maxiter:
            mb_max_iter = st.number_input('Max Iterations', value=100, min_value=1, max_value=500, step=10)

        # 2) Method B 분석 미리보기 (항상 표시 / Expander)
        with st.expander("Method B 분석 결과 (Leontief 급수전개)", expanded=False):
             if 'df_for_leontief_with_label' in st.session_state:
                 mb_N, mb_N0, mb_fig, mb_info = extract_network_leontief(
                     st.session_state['df_for_leontief_with_label'].iloc[2:, 2:],
                     epsilon=mb_epsilon, delta=mb_delta, max_iter=mb_max_iter
                 )
                 st.pyplot(mb_fig)
                 status_msg = "수렴 완료 (Converged)" if mb_info['converged'] else "최대 반복 도달 (Max Iter)"
                 st.markdown(f"""
                 **Method B 추출 결과**
                 - **최종 반복 횟수 (t):** `{mb_info['final_t']}` ({status_msg})
                 - **최종 Density (θ):** `{mb_info['last_density']:.2f}`
                 - **마지막 Change Ratio (r):** `{mb_info['last_ratio']:.6f}` (기준: δ = {mb_info['delta']})
                 """)
                 st.session_state['res_method_b'] = (mb_N, mb_N0, mb_fig, mb_info)


        st.subheader("2-1. 네트워크 추출 방식 선택")
        method_option = st.radio(
            "분석 모드 선택",
            [
                "Method A: 최적 임계값 (Threshold Optimization)", 
                "Method B: Leontief 급수전개 (Series Expansion)"
            ],
            index=0,
            label_visibility="collapsed", # 상단 subheader가 있으므로 라벨 숨김
            on_change=reset_threshold_state,  # <--- [핵심] 값이 바뀌면 위 함수 실행 -> 결과 초기화
            help="Method A는 거리 최소화 및 연결성 기반으로 임계값을 찾습니다. Method B는 Leontief 급수전개를 통해 구조적 수렴 시점의 네트워크를 추출합니다."
        )

        # ---------------------------------------------------------------------
        # 3. [Standardization] 선택에 따라 'final_network_matrix' 결정
        # ---------------------------------------------------------------------
        final_network_matrix = None

        if method_option.startswith("Method A"):
            st.info("📊 **Method A 분석 결과**")
            st.write("🔹 이 방식은 거리 최소화 및 연결성을 기반으로 최적 임계값을 제안합니다.")
            st.caption("👉 그래프를 참고하여 임계값을 설정하면, 해당 값 이하의 연결은 제거됩니다.")
            
            # Layout: Graph (Left) vs Controls (Right)
            col_graph, col_controls = st.columns([2, 1])
            
            with col_graph:
                st.markdown("##### 1️⃣ Threshold에 따른 생존비율 그래프")
                suggested_val = 0.0
                if 'df_for_leontief_with_label' in st.session_state:
                     # threshold_count 함수는 그래프를 그리고, 분석 결과를 Markdown으로 출력하며, 제안값(float)을 반환함
                     suggested_val = threshold_count(st.session_state['df_for_leontief_with_label'].iloc[2:, 2:])
            
            with col_controls:
                st.markdown("##### 2️⃣ 임계값 설정")
                st.info(f"좌측 분석 결과를 참고하여\n임계값을 입력하세요.\n\n**제안값:** `{suggested_val:.4f}`")
                
                # 텍스트 입력창 (기본값은 0.000이지만, 제안값을 참고하도록 안내)
                input_val = st.text_input(
                    '임계값 (Threshold)', 
                    value='0.000',
                    help=f"그래프의 Final Decision ({suggested_val:.4f}) 값을 입력하면 최적화된 결과를 얻을 수 있습니다."
                )
                threshold_val = float(input_val) if input_val else 0.0
                
                st.write("") # Margin
                
                if st.button('설정 적용하기 (Apply)', type="primary", use_container_width=True):
                    # 버튼을 눌러야만 비로소 session_state에 등록되어 아래 결과창이 열림
                    st.session_state.threshold = threshold_val
                    st.session_state.threshold_cal = True
                    st.rerun() # 상태 업데이트 후 즉시 리런하여 아래 결과창 표시

            st.markdown("---")


            if 'threshold' in st.session_state and st.session_state.show_edited:
                if st.session_state.threshold_cal:
                    # binary matrix 생성
                    binary_matrix = make_binary_matrix(st.session_state['df_for_leontief_with_label'].iloc[2:, 2:].apply(pd.to_numeric, errors='coerce'), st.session_state.threshold)
                    _, binary_matrix = separate_diagonals(binary_matrix)
                    binary_matrix_with_label = st.session_state['df_for_leontief'].copy()
                    binary_matrix_with_label.iloc[2:,2:] = binary_matrix


                    filtered_matrix_X = st.session_state['df_for_leontief'].copy()
                    filtered_matrix_X.iloc[2:, 2:] = filtered_matrix_X.iloc[2:, 2:].apply(pd.to_numeric, errors='coerce')*binary_matrix

                    filtered_normalized = st.session_state['df_normalized_with_label']
                    filtered_normalized.iloc[2:, 2:] = st.session_state['df_normalized_with_label'].iloc[2:, 2:].apply(pd.to_numeric, errors='coerce')*binary_matrix

                    filtered_leontief = st.session_state['df_for_leontief_with_label']
                    filtered_leontief.iloc[2:, 2:] = st.session_state['df_for_leontief_with_label'].iloc[2:, 2:].apply(pd.to_numeric, errors='coerce')*binary_matrix

                    G_tn = nx.DiGraph()

                    # 모든 노드 가져오기 (고립된 노드 포함)
                    all_nodes_tn = set(range(filtered_leontief.iloc[2:, 2:].shape[0]))
                    G_tn.add_nodes_from(all_nodes_tn)  # 모든 노드 추가 (고립 노드 포함)

                    rows_tn, cols_tn = np.where(filtered_leontief.iloc[2:, 2:] != 0)
                    weights_tn = filtered_leontief.iloc[2:, 2:].to_numpy()[rows_tn, cols_tn]
                    edges_tn = [(j, i, {'weight': w}) for i, j, w in zip(rows_tn, cols_tn, weights_tn)]
                    G_tn.add_edges_from(edges_tn)


                    tn_cents = calculate_network_centralities(G_tn, st.session_state['df_normalized_with_label'],True)
                    tn_df_degree, tn_df_bc, tn_df_cc, tn_df_ev, tn_df_hi,tn_df_kim, tn_gd_in_mean, tn_gd_in_std, tn_gd_out_mean, tn_gd_out_std, tn_bc_mean, tn_bc_std, tn_cc_in_mean, tn_cc_in_std, tn_cc_out_mean, tn_cc_out_std, tn_ev_in_mean, tn_ev_in_std, tn_ev_out_mean, tn_ev_out_std, tn_hub_mean, tn_hub_std, tn_ah_mean, tn_ah_std, tn_const_mean,tn_const_std, tn_eff_mean, tn_eff_std = tn_cents

                    tbn_cents = calculate_network_centralities(G_tn, st.session_state['df_normalized_with_label'],False)
                    tbn_df_degree, tbn_df_bc, tbn_df_cc, tbn_df_ev, tbn_df_hi,tbn_df_kim, tbn_gd_in_mean, tbn_gd_in_std, tbn_gd_out_mean, tbn_gd_out_std, tbn_bc_mean, tbn_bc_std, tbn_cc_in_mean, tbn_cc_in_std, tbn_cc_out_mean, tbn_cc_out_std, tbn_ev_in_mean, tbn_ev_in_std, tbn_ev_out_mean, tbn_ev_out_std, tbn_hub_mean, tbn_hub_std, tbn_ah_mean, tbn_ah_std, tbn_const_mean, tbn_const_std, tbn_eff_mean, tbn_eff_std = tbn_cents

                st.subheader('Threshold 적용 후 Filtered matrices')

                col1, col2, col3, col4 = st.tabs(['Filtered_leontief', 'Binary_matrix','Filtered_matrix','Filtered_Normalized'])
                with col1:
                    st.write(filtered_leontief)
                    st.markdown("##### Threshold 적용 후 네트워크 행렬의 지표")
                    render_centrality_tabs(tn_cents, weighted=True, key_prefix="tn")

                with col2:
                    st.write(binary_matrix_with_label)
                    # 1. 노드 이름(A, B, C01, ...) 리스트로 추출
                    #    binary_matrix_with_label 의 2번째 행부터 첫 번째 열(0번) 값을 가져옵니다.
                    node_names_tn = binary_matrix_with_label.iloc[2:, 0].tolist()

                    # 2. 레이아웃 계산
                    pos_tn = nx.spring_layout(G_tn, seed=42)

                    # 3. 시각화
                    fig_tn, ax_tn = plt.subplots(figsize=(8, 6))
                    nx.draw_networkx_nodes(G_tn, pos_tn, node_size=400, ax=ax_tn)
                    nx.draw_networkx_edges(G_tn, pos_tn, arrowstyle='->', arrowsize=10, ax=ax_tn)

                    # 4. 레이블 매핑 (노드 번호 → 실제 이름)
                    label_dict_tn = {i: name for i, name in enumerate(node_names_tn)}

                    # 5. 레이블 그리기
                    nx.draw_networkx_labels(G_tn, pos_tn, labels=label_dict_tn, font_size=10, ax=ax_tn)

                    ax_tn.set_title("Thresholded Binary Network (TBN)", fontsize=14)
                    ax_tn.axis('off')
                    st.pyplot(fig_tn)

                    st.markdown("##### 이진 방향성 네트워크 행렬의 지표")
                    render_centrality_tabs(tbn_cents, weighted=False, key_prefix="tbn")
                with col3:
                    st.write(filtered_matrix_X)
                with col4:
                    st.write(filtered_normalized)


                with st.sidebar.expander(f"filtered file(threshold:{st.session_state.threshold})"):
                    threshold_original = {
                    "threshold_original_degree_centrality": tn_df_degree,
                    "threshold_original_betweenness_centrality": tn_df_bc,
                    "threshold_original_closeness_centrality": tn_df_cc,
                    "threshold_original_eigenvector_centrality": tn_df_ev,
                    "threshold_original_hits": tn_df_hi,
                    "threshold_original_constraints&efficiencies": tn_df_kim
                                            }
                    threshold_bn = {
                    "threshold_bn_degree_centrality": tbn_df_degree,
                    "threshold_bn_betweenness_centrality": tbn_df_bc,
                    "threshold_bn_closeness_centrality": tbn_df_cc,
                    "threshold_bn_eigenvector_centrality": tbn_df_ev,
                    "threshold_bn_hits": tbn_df_hi,
                    "threshold_bn_constraints&efficiencies": tbn_df_kim
                                            }
                    
                    # 모든 결과를 한 dict으로 합치기
                    all_threshold = {
                        "filtered_leontief(threshold)":        filtered_leontief,
                        **threshold_original,
                        "binary_matrix(threshold)":            binary_matrix_with_label,
                        **threshold_bn,
                        "filtered_matrix_X(threshold)":        filtered_matrix_X,
                        "filtered_normalized(threshold)":      filtered_normalized
                    }
                    # ZIP으로 한 번에 다운로드
                    download_multiple_csvs_as_zip(
                        all_threshold,
                        zip_name="threshold 적용 전체 결과들(zip)"
                    )
                    donwload_data(filtered_leontief, 'filtered_leontief(threshold)')
                    download_multiple_csvs_as_zip(threshold_original, zip_name="threshold 적용 네트워크의 지표들(zip)")
                    donwload_data(binary_matrix_with_label, 'binary_matrix(threshold)')
                    download_multiple_csvs_as_zip(threshold_bn, zip_name="threshold 적용 BN 네트워크의 지표들(zip)")
                    donwload_data(filtered_matrix_X, 'filtered_matrix_X(threshold)')
                    donwload_data(filtered_normalized, 'filtered_normalized(threshold)')

        else:
            # -----------------------------------------------------------------
            # [Method B] Leontief 급수전개 (Series Expansion)
            # -----------------------------------------------------------------
            st.info("📊 **Method B 분석 결과 (Leontief 급수전개)**")
            st.write("🔹 이 방식은 Leontief Inverse의 급수 전개를 통해 **구조적 수렴 시점의 네트워크**를 추출합니다.")
            st.caption("👉 ε(epsilon)과 δ(delta)를 상단에서 조절하여 네트워크 밀도와 수렴 기준을 설정할 수 있습니다.")

            if 'res_method_b' in st.session_state:
                mb_N, mb_N0, mb_fig, mb_info = st.session_state['res_method_b']

                # 수렴 그래프 표시
                st.pyplot(mb_fig)

                # 수렴 정보 표시
                status_msg = "수렴 완료 (Converged)" if mb_info['converged'] else "최대 반복 도달 (Max Iter)"
                st.markdown(f"""
                **Method B 추출 결과 요약**
                - **최종 반복 횟수 (t):** `{mb_info['final_t']}` ({status_msg})
                - **최종 Density (θ):** `{mb_info['last_density']:.2f}`
                - **마지막 Change Ratio (r):** `{mb_info['last_ratio']:.6f}` (기준: δ = {mb_info['delta']})
                - **ε (epsilon):** `{mb_info['epsilon']}`
                """)

                # Method B의 결과 행렬(가중치 네트워크)을 final_network_matrix로 할당
                final_network_matrix = mb_N.copy()
                st.session_state.delta = mb_info['delta']
            else:
                st.warning("⚠️ Method B 결과가 아직 생성되지 않았습니다. 상단의 Expander에서 미리보기를 확인하세요.")

        # ---------------------------------------------------------------------
        # 4. [Common Output] 결과 통합 및 시각화 (공통 로직)
        # ---------------------------------------------------------------------
        
        if final_network_matrix is not None:
            # ---------------------------------------------------------------------
            # 4. [Common Output] 결과 통합 및 시각화 (공통 로직)
            # ---------------------------------------------------------------------
            
            # (1) Binary Matrix 생성 (0보다 크면 1, 아니면 0)
            binary_matrix = (final_network_matrix > 0).astype(int)

            # (2) DataFrame 매핑 (시각화 및 다운로드용)
            # 레이블이 있는 형태 유지를 위해 기존 df 구조 사용 (df_normalized_with_label 껍데기 복사)
            
            filtered_matrix_df = st.session_state['df_normalized_with_label'].copy()
            filtered_matrix_df.iloc[2:, 2:] = final_network_matrix
            
            binary_matrix_df = st.session_state['df_normalized_with_label'].copy()
            binary_matrix_df.iloc[2:, 2:] = binary_matrix

            # (3) 결과 표시
            st.write(f"**현재 적용된 네트워크:** {method_option}")
            
            col_res1, col_res2 = st.tabs(["가중치 네트워크(Weighted)", "이진 네트워크(Binary)"])
            with col_res1:
                st.dataframe(filtered_matrix_df)
            with col_res2:
                st.dataframe(binary_matrix_df)

            # ---------------------------------------------------------------------
            # 5. [Downstream] 그래프 생성 (NetworkX) - 기존 로직 연결용
            # ---------------------------------------------------------------------
            # G_tn: Weighted Graph
            G_tn = nx.DiGraph()
            all_nodes_tn = set(range(final_network_matrix.shape[0]))
            G_tn.add_nodes_from(all_nodes_tn)
            
            rows_tn, cols_tn = np.where(final_network_matrix > 0)
            weights_tn = final_network_matrix[rows_tn, cols_tn]
            edges_tn = [(j, i, {'weight': w}) for i, j, w in zip(rows_tn, cols_tn, weights_tn)]
            G_tn.add_edges_from(edges_tn)
            G_n = G_tn # Alias for downstream compatibility

            # G_bn: Binary Graph
            G_bn = nx.DiGraph()
            G_bn.add_nodes_from(all_nodes_tn)
            rows_bn, cols_bn = np.where(binary_matrix > 0)
            edges_bn = [(j, i) for i, j in zip(rows_bn, cols_bn)]
            G_bn.add_edges_from(edges_bn)

            # 3. 중앙성 계산 (기존 로직 복원)
            n_cents = calculate_network_centralities(G_n, st.session_state['df_normalized_with_label'],True)
            n_df_degree, n_df_bc, n_df_cc, n_df_ev, n_df_hi, n_df_kim, n_gd_in_mean, n_gd_in_std, n_gd_out_mean, n_gd_out_std, n_bc_mean, n_bc_std, n_cc_in_mean, n_cc_in_std, n_cc_out_mean, n_cc_out_std, n_ev_in_mean, n_ev_in_std, n_ev_out_mean, n_ev_out_std, n_hub_mean, n_hub_std, n_ah_mean, n_ah_std, n_const_mean,n_const_std, n_eff_mean, n_eff_std = n_cents

            bn_cents = calculate_network_centralities(G_bn, st.session_state['df_normalized_with_label'],False)
            bn_df_degree, bn_df_bc, bn_df_cc, bn_df_ev, bn_df_hi, bn_df_kim, bn_gd_in_mean, bn_gd_in_std, bn_gd_out_mean, bn_gd_out_std, bn_bc_mean, bn_bc_std, bn_cc_in_mean, bn_cc_in_std, bn_cc_out_mean, bn_cc_out_std, bn_ev_in_mean, bn_ev_in_std, bn_ev_out_mean, bn_ev_out_std, bn_hub_mean, bn_hub_std, bn_ah_mean, bn_ah_std, bn_const_mean,bn_const_std, bn_eff_mean, bn_eff_std = bn_cents

            # 4. UN 및 Label DataFrames 생성 (시각화용)
            # BN이 확실히 존재하는 블록 내부에서 UN 생성
            BN = binary_matrix
            UN = create_undirected_network(BN)
            
            win_N_final_label = filtered_matrix_df
            win_BN_final_label = binary_matrix_df
            win_UN_final_label = st.session_state['df_normalized_with_label'].copy()
            win_UN_final_label.iloc[2:,2:]= UN

            # ---------------------------------------------------------------------
            # [Visualization] 기존 시각화 코드 (Unindented)
            # ---------------------------------------------------------------------
            col1_net, col2_net, col3_net = st.tabs([f"임계치 적용 후 네트워크 행렬", '이진화된 방향성 네트워크 (BN)', '무방향 이진 네트워크 (UN)'])
            with col1_net:
                st.write(win_N_final_label)
                st.markdown("##### 임계치 적용 후 네트워크 행렬의 지표")
                render_centrality_tabs(n_cents, weighted=True, key_prefix="n")

            with col2_net:
                st.write(win_BN_final_label)
                    # 1. 노드 이름(A, B, C01, ...) 리스트로 추출
                # win_BN_final_label 의 2번째 열(인덱스 0)에 실제 노드명이 들어있다고 가정
                node_names_delta = win_BN_final_label.iloc[2:, 0].tolist()  

                # 3. 레이아웃 계산
                pos = nx.spring_layout(G_bn, seed=42)

                # 4. 시각화
                fig, ax = plt.subplots(figsize=(8, 6))
                nx.draw_networkx_nodes(G_bn, pos, node_size=400, ax=ax)
                nx.draw_networkx_edges(G_bn, pos, arrowstyle='->', arrowsize=10, ax=ax)

                # 5. 레이블 매핑 (노드 번호 → 실제 이름)
                label_dict = {i: name for i, name in enumerate(node_names_delta)}

                # 6. 레이블 그리기
                nx.draw_networkx_labels(G_bn, pos, labels=label_dict, font_size=10, ax=ax)

                ax.set_title("Delta-Thresholded Binary Network (DBN)", fontsize=14)
                ax.axis('off')
                st.pyplot(fig)




                st.markdown("##### 이진 방향성 네트워크 행렬의 지표")
                render_centrality_tabs(bn_cents, weighted=False, key_prefix="bn")

            with col3_net:
                st.write(win_UN_final_label)


            with st.sidebar.expander(f"filtered file(delta:{st.session_state.delta})"):
                delta_original = {
                "delta_original_degree_centrality": n_df_degree,
                "delta_original_betweenness_centrality": n_df_bc,
                "delta_original_closeness_centrality": n_df_cc,
                "delta_original_eigenvector_centrality": n_df_ev,
                "delta_original_hits": n_df_hi,
                "delta_original_constraints&efficiencies": n_df_kim
                                        }
                delta_bn = {
                "delta_bn_degree_centrality": bn_df_degree,
                "delta_bn_betweenness_centrality": bn_df_bc,
                "delta_bn_closeness_centrality": bn_df_cc,
                "delta_bn_eigenvector_centrality": bn_df_ev,
                "delta_bn_hits": bn_df_hi,
                "delta_bn_constraints&efficiencies": bn_df_kim
                                        }
                
                all_delta = {
                "filtered_matrix_X(delta)":          win_N_final_label,
                **delta_original,
                "binary_matrix(delta)":              win_BN_final_label,
                **delta_bn,
                "undirected_binary_matrix(delta)":   win_UN_final_label
                }

                download_multiple_csvs_as_zip(
                    all_delta,
                    zip_name="delta 적용 전체 결과들(zip)"
                )
                donwload_data(win_N_final_label, 'filtered_matrix_X(delta)')
                download_multiple_csvs_as_zip(delta_original, zip_name="delta 적용 네트워크의 지표들(zip)")
                donwload_data(win_BN_final_label, 'binary_matrix(delta)')
                download_multiple_csvs_as_zip(delta_bn, zip_name="delta 적용 BN 네트워크의 지표들(zip)")
                donwload_data(win_UN_final_label, 'undirected_binary_matrix(delta)')






    
            # [공통] 필요한 곳에 한 번만 넣어 두세요
    def _gather_all_dataframes() -> dict[str, pd.DataFrame]:
        """session_state 안에 존재하는 모든 DataFrame을 한 ZIP으로 묶을 dict 생성"""
        dfs: dict[str, pd.DataFrame] = {}

        # 1) 최초 업로드 원본
        if 'df' in st.session_state:
            dfs['uploaded_df']          = st.session_state['df']
            if 'mid_ID_idx' in st.session_state:
                dfs['uploaded_matrix_X'] = get_submatrix_withlabel(
                    st.session_state['df'], first_idx[0], first_idx[1],
                    st.session_state['mid_ID_idx'][0], st.session_state['mid_ID_idx'][1],
                    first_idx, numberoflabel=number_of_label)
                dfs['uploaded_matrix_R'] = get_submatrix_withlabel(
                    st.session_state['df'], st.session_state['mid_ID_idx'][0]+1, first_idx[1],
                    st.session_state['df'].shape[0]-1, st.session_state['mid_ID_idx'][1],
                    first_idx, numberoflabel=number_of_label)
                dfs['uploaded_matrix_C'] = get_submatrix_withlabel(
                    st.session_state['df'], first_idx[0], st.session_state['mid_ID_idx'][1]+1,
                    st.session_state['mid_ID_idx'][0], st.session_state['df'].shape[1]-1,
                    first_idx, numberoflabel=number_of_label)

        # 2) 편집 완료본
        if 'df_edited' in st.session_state and 'edited_matrix_X' in locals():
            dfs['edited_df']           = st.session_state['df_edited']
            dfs['edited_matrix_X']     = edited_matrix_X
            dfs['edited_matrix_R']     = edited_matrix_R
            dfs['edited_matrix_C']     = edited_matrix_C

        # 3) Leontief 관련
        if 'df_for_leontief_with_label' in st.session_state:
            dfs['투입계수행렬']             = st.session_state['df_normalized_with_label']
            dfs['leontief_inverse']        = st.session_state['df_for_leontief_with_label']
            dfs['FL_BL']                   = st.session_state['fl_bl']
            dfs['부가가치계수행렬']          = st.session_state['df_for_r_with_label']
            dfs['부가가치계벡터']            = st.session_state['added_value_denominator']
            dfs['normalization_denominator'] = st.session_state['normalization_denominator']

        # 4) delta 필터 결과
        if 'delta' in st.session_state and 'win_N_final_label' in locals(): 
            dfs['filtered_matrix_X(delta)']      = win_N_final_label
            dfs['binary_matrix(delta)']          = win_BN_final_label
            dfs['undirected_binary_matrix(delta)'] = win_UN_final_label
            dfs.update({                         # 지표들
                'delta_original_degree_centrality':      n_df_degree,
                'delta_original_betweenness_centrality': n_df_bc,
                'delta_original_closeness_centrality':   n_df_cc,
                'delta_original_eigenvector_centrality': n_df_ev,
                'delta_original_hits':                  n_df_hi,
                "delta_original_constraints&efficiencies": n_df_kim,
                'delta_bn_degree_centrality':           bn_df_degree,
                'delta_bn_betweenness_centrality':      bn_df_bc,
                'delta_bn_closeness_centrality':        bn_df_cc,
                'delta_bn_eigenvector_centrality':      bn_df_ev,
                'delta_bn_hits':                        bn_df_hi,
                "delta_bn_constraints&efficiencies":    bn_df_kim
            })

        # 5) threshold 필터 결과
        if 'threshold' in st.session_state and 'binary_matrix_with_label' in locals():
            dfs['filtered_leontief(threshold)']   = filtered_leontief
            dfs['binary_matrix(threshold)']       = binary_matrix_with_label
            dfs['filtered_matrix_X(threshold)']   = filtered_matrix_X
            dfs['filtered_normalized(threshold)'] = filtered_normalized
            dfs.update({
                'threshold_original_degree_centrality':      tn_df_degree,
                'threshold_original_betweenness_centrality': tn_df_bc,
                'threshold_original_closeness_centrality':   tn_df_cc,
                'threshold_original_eigenvector_centrality': tn_df_ev,
                'threshold_original_hits':                  tn_df_hi,
                "threshold_original_constraints&efficiencies": tn_df_kim,
                'threshold_bn_degree_centrality':           tbn_df_degree,
                'threshold_bn_betweenness_centrality':      tbn_df_bc,
                'threshold_bn_closeness_centrality':        tbn_df_cc,
                'threshold_bn_eigenvector_centrality':      tbn_df_ev,
                'threshold_bn_hits':                        tbn_df_hi,
                "threshold_bn_constraints&efficiencies":    tbn_df_kim
            })

        return dfs
    with st.sidebar.expander("전체 결과 ZIP 다운로드"):
        all_dfs = _gather_all_dataframes()
        if all_dfs:
            download_multiple_csvs_as_zip(all_dfs, zip_name="IO_analysis_all_results(zip)")

        else:
            st.write("아직 저장된 결과가 없습니다. 먼저 분석을 실행하세요.")
    st.sidebar.header('수정내역')
    with st.sidebar.expander('수정내역 보기'):
        st.text(st.session_state['data_editing_log'])

if __name__ == "__main__":
    main()
