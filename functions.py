"""하위호환 shim.

백엔드 코드는 이제 `iolib` 패키지로 분리되어 있다. 기존 `from functions import *`
호출부(app.py 등)가 그대로 동작하도록, 여기서 패키지의 모든 공개 이름을 재노출한다.
새 코드는 `iolib` 에서 직접 import 하는 것을 권장한다.

모듈 매핑:
    iolib.loading      — load_data, convert_df, get_submatrix_withlabel, get_mid_ID_idx
    iolib.batch_upload — prepare_batch_preview
    iolib.editing      — insert_row_and_col, transfer_to_new_sector, remove_zero_series,
                         reduce_negative_values, apply_batch_edit, replay_edit_ops_on_df
    iolib.leontief     — build_leontief_outputs, compute_leontief_inverse, separate_diagonals,
                         make_binary_matrix, filter_matrix, threshold_network,
                         create_binary_network, create_undirected_network, make_col, make_table
    iolib.network      — calculate_network_centralities, threshold_count,
                         extract_network_leontief, calculate_kim_metrics, calculate_standard_metrics
    iolib.download     — donwload_data, make_zip_bytes, download_multiple_csvs_as_zip
"""
from iolib import *          # noqa: F401,F403
from iolib import __all__    # noqa: F401
