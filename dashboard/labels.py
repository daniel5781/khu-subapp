"""결과 파일 식별자와 화면의 읽기 쉬운 이름을 연결한다."""

RESULT_LABELS = {
    "uploaded_df": "원본 · 총거래표",
    "uploaded_df_local": "원본 · 국산거래표",
    "uploaded_matrix_X": "원본 · 중간거래 X",
    "uploaded_matrix_R": "원본 · 최종수요 R",
    "uploaded_matrix_C": "원본 · 본원투입 C",
    "edited_df": "편집본 · 총거래표",
    "edited_df_local": "편집본 · 국산거래표",
    "edited_matrix_X": "편집본 · 중간거래 X",
    "edited_matrix_R": "편집본 · 최종수요 R",
    "edited_matrix_C": "편집본 · 본원투입 C",
    "normalization_denominator": "정규화 분모 · 총투입계",
    "투입계수행렬": "투입계수행렬 A",
    "국산투입계수행렬": "국산 투입계수행렬",
    "leontief_inverse": "레온티에프 역행렬 L",
    "국산_leontief_inverse": "국산 레온티에프 역행렬",
    "FL_BL": "전·후방 연쇄효과 (FL / BL)",
    "g_series": "생산유발 구성 (g1 / g2 / g3)",
    "GDP": "GDP 유발액",
    "부가가치유발효과": "국내 부가가치 유발효과",
    "부가가치계수행렬": "부가가치계수행렬",
    "부가가치계벡터": "산업별 부가가치",
    "network_weighted": "가중치 네트워크",
    "network_binary": "이진 네트워크",
    "network_undirected": "무방향 네트워크",
    "filtered_transactions": "추출된 연결 · 거래액",
    "filtered_coefficients": "추출된 연결 · 투입계수",
}


def result_label(name):
    if name in RESULT_LABELS:
        return RESULT_LABELS[name]
    for prefix, label in (("weighted_", "가중치"), ("binary_", "이진")):
        if name.startswith(prefix):
            metric = name[len(prefix) :]
            title = {
                "degree": "연결 중심성",
                "betweenness": "매개 중심성",
                "closeness": "근접 중심성",
                "eigenvector": "고유벡터 중심성",
                "hits": "Hub / Authority",
                "structural_holes": "구조적 공백",
            }.get(metric, metric)
            return f"{label} · {title}"
    return name
