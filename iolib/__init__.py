"""iolib — 산업연관(I/O) 네트워크 분석 백엔드.

기존 단일 파일 `functions.py`(1,300여 줄)를 역할별 모듈로 분리한 패키지.
`app.py` 는 `from functions import *` (하위호환 shim) 또는 `from iolib import *`
로 동일한 이름을 그대로 사용할 수 있다.

모듈 구성
---------
- loading       : 엑셀 로딩, 서브매트릭스 추출, 중간수요 경계(mid_ID_idx) 탐지
- batch_upload  : 엑셀/ZIP 일괄편집 파일 파싱·미리보기
- editing       : 부문 편집 연산(추가/이전/삭제/음수보정)과 재생(replay)
- leontief      : 투입계수행렬·Leontief 역행렬·행렬 전처리·표 생성
- network       : 네트워크 추출(Method A/B)·중심성·구조적 공백 지표
- download      : Streamlit 다운로드 버튼(CSV/ZIP)
"""

from .loading import (
    load_data,
    convert_df,
    get_submatrix_withlabel,
    get_mid_ID_idx,
)
from .batch_upload import (
    prepare_batch_preview,
)
from .editing import (
    insert_row_and_col,
    transfer_to_new_sector,
    remove_zero_series,
    reduce_negative_values,
    apply_batch_edit,
    replay_edit_ops_on_df,
)
from .leontief import (
    make_binary_matrix,
    filter_matrix,
    compute_leontief_inverse,
    separate_diagonals,
    threshold_network,
    create_binary_network,
    create_undirected_network,
    build_leontief_outputs,
    make_col,
    make_table,
)
from .network import (
    calculate_network_centralities,
    threshold_count,
    extract_network_leontief,
    calculate_kim_metrics,
    calculate_standard_metrics,
)
from .download import (
    donwload_data,
    make_zip_bytes,
    download_multiple_csvs_as_zip,
    render_japan_data_sidebar,
)

__all__ = [
    # loading
    "load_data", "convert_df", "get_submatrix_withlabel", "get_mid_ID_idx",
    # batch_upload
    "prepare_batch_preview",
    # editing
    "insert_row_and_col", "transfer_to_new_sector", "remove_zero_series",
    "reduce_negative_values", "apply_batch_edit", "replay_edit_ops_on_df",
    # leontief
    "make_binary_matrix", "filter_matrix", "compute_leontief_inverse",
    "separate_diagonals", "threshold_network", "create_binary_network",
    "create_undirected_network", "build_leontief_outputs", "make_col", "make_table",
    # network
    "calculate_network_centralities", "threshold_count", "extract_network_leontief",
    "calculate_kim_metrics", "calculate_standard_metrics",
    # download
    "donwload_data", "make_zip_bytes", "download_multiple_csvs_as_zip",
    "render_japan_data_sidebar",
]
