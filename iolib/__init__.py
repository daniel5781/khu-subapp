"""산업연관 분석 라이브러리. import 시 Streamlit이나 matplotlib를 요구하지 않는다.

주요 진입점: load_workbook → EditingSession → analyze_tables → analyze_network.
기존 functions.py API도 호환을 위해 유지한다.
"""

__version__ = "0.1.0"

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
    "load_data",
    "convert_df",
    "get_submatrix_withlabel",
    "get_mid_ID_idx",
    # batch_upload
    "prepare_batch_preview",
    # editing
    "insert_row_and_col",
    "transfer_to_new_sector",
    "remove_zero_series",
    "reduce_negative_values",
    "apply_batch_edit",
    "replay_edit_ops_on_df",
    # leontief
    "make_binary_matrix",
    "filter_matrix",
    "compute_leontief_inverse",
    "separate_diagonals",
    "threshold_network",
    "create_binary_network",
    "create_undirected_network",
    "build_leontief_outputs",
    "make_col",
    "make_table",
    # network
    "calculate_network_centralities",
    "threshold_count",
    "extract_network_leontief",
    "calculate_kim_metrics",
    "calculate_standard_metrics",
    # download
    "donwload_data",
    "make_zip_bytes",
    "download_multiple_csvs_as_zip",
    "render_japan_data_sidebar",
]


from .preprocessing import load_workbook, get_mode_params, available_us_years
from .session import EditingSession
from .analysis import analyze_tables, AnalysisResult
from .leontief import calculate_leontief, LeontiefResult
from .network import analyze_threshold, extract_series_network, graph_from_matrix
from .network_analysis import analyze_network, NetworkResult

__all__ += [
    "load_workbook",
    "get_mode_params",
    "available_us_years",
    "EditingSession",
    "analyze_tables",
    "AnalysisResult",
    "calculate_leontief",
    "LeontiefResult",
    "analyze_threshold",
    "extract_series_network",
    "graph_from_matrix",
    "analyze_network",
    "NetworkResult",
]
