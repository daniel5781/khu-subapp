"""문자 라벨과 숫자가 섞인 원표를 Arrow 오류 없이 표시한다."""

import pandas as pd
import streamlit as st


def display_frame(frame):
    if not isinstance(frame, (pd.DataFrame, pd.Series)):
        return frame
    result = frame.to_frame() if isinstance(frame, pd.Series) else frame.copy()
    result.columns = result.columns.map(str)
    for column in result.columns:
        values = result[column].dropna()
        has_text = values.map(lambda value: isinstance(value, str))
        if has_text.any():
            result[column] = result[column].map(
                lambda value: None if pd.isna(value) else str(value)
            )
    return result


def show_table(frame, **kwargs):
    return st.dataframe(display_frame(frame), **kwargs)
