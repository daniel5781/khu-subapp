"""구버전 다운로드 API. 화면 구현은 dashboard.downloads로 이동했다."""

from .exports import make_zip_bytes as make_zip_bytes


def donwload_data(df, file_name):
    from dashboard.downloads import download_data

    return download_data(df, file_name)


def download_multiple_csvs_as_zip(dfs, zip_name):
    from dashboard.downloads import download_multiple_csvs_as_zip as render

    return render(dfs, zip_name)


def render_japan_data_sidebar():
    from dashboard.downloads import render_japan_data_sidebar as render

    return render()
