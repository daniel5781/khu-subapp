"""CSV와 ZIP 직렬화. UI 없이 노트북·CLI·배치 작업에서도 사용한다."""

import io
import zipfile
import pandas as pd


def make_zip_bytes(dfs: dict[str, pd.DataFrame]) -> bytes:
    """
    dfs: dict where keys are desired CSV filenames and values are DataFrames.
    반환값: ZIP 파일의 바이너리
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, df in dfs.items():
            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            zf.writestr(f"{fname}.csv", csv_bytes)
    return buf.getvalue()


def collect_result_frames(editor, analysis=None, network_frames=None):
    from iolib.analysis import partition_table

    if editor is None:
        return {}
    original = editor.original
    frames = {"uploaded_df": original.df, "uploaded_df_local": original.df_local}
    frames.update(
        {
            f"uploaded_{name}": frame
            for name, frame in partition_table(
                original.df, editor.params.first_idx, original.mid_ID_idx
            ).items()
        }
    )
    frames.update({"edited_df": editor.total, "edited_df_local": editor.domestic})
    frames.update(
        {
            f"edited_{name}": frame
            for name, frame in partition_table(
                editor.total, editor.params.first_idx, editor.mid
            ).items()
        }
    )
    if analysis is not None:
        frames.update(analysis.frames)
        frames.update(network_frames or {})
    return frames
