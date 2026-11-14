"""대시보드 배치. 모든 콜백 대상은 탭 전환과 무관하게 유지된다."""

from dash import dcc, html
import dash_ag_grid as dag
from iolib.config import MODES
from iolib.resources import japan_resource_options
from .figures import empty_figure

GRAPH_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "toImageButtonOptions": {"format": "png", "filename": "khu-analysis", "scale": 2},
}


def field(label, control, hint=None):
    return html.Div(
        [
            html.Label(label, htmlFor=getattr(control, "id", None)),
            control,
            html.Small(hint) if hint else None,
        ],
        className="field",
    )


def number(id, value, minimum=None, maximum=None, step="any"):
    return dcc.Input(
        id=id,
        type="number",
        value=value,
        min=minimum,
        max=maximum,
        step=step,
        debounce=True,
    )


def button(label, id, primary=False):
    return html.Button(
        label, id=id, n_clicks=0, className="button primary" if primary else "button"
    )


def grid(id, height=420):
    return dag.AgGrid(
        id=id,
        rowData=[],
        columnDefs=[],
        className="ag-theme-quartz",
        defaultColDef={"filter": True, "sortable": True, "resizable": True},
        dashGridOptions={
            "theme": "legacy",
            "pagination": True,
            "paginationPageSize": 25,
            "paginationPageSizeSelector": [25, 50, 100],
            "rowHeight": 34,
        },
        style={"height": f"{height}px", "width": "100%"},
    )


def graph(id):
    return dcc.Graph(id=id, figure=empty_figure(), config=GRAPH_CONFIG)


def card(title, children, subtitle=None):
    return html.Section(
        [
            html.Div(
                [html.H3(title), html.P(subtitle) if subtitle else None],
                className="card-heading",
            ),
            *children,
        ],
        className="card",
    )


def build_layout(pointer):
    resources = japan_resource_options()
    sidebar = html.Aside(
        [
            html.Div(
                [
                    html.Span("K", className="brand-mark"),
                    html.Div(
                        [html.Strong("KHU · IO LAB"), html.Small("산업연관 분석")]
                    ),
                ],
                className="brand",
            ),
            html.Div("분석 데이터", className="sidebar-label"),
            field(
                "국가 · 표 형식",
                dcc.Dropdown(
                    id="mode",
                    options=[{"label": m, "value": m} for m in MODES],
                    value=MODES[0],
                    clearable=False,
                ),
            ),
            field(
                "미국 자료 연도",
                dcc.Dropdown(
                    id="year",
                    options=[],
                    value=None,
                    disabled=True,
                    clearable=False,
                    placeholder="미국 모드에서 선택",
                ),
            ),
            html.Div(
                [
                    field("숫자 시작 행", number("manual-row", 7, 3, step=1)),
                    field("숫자 시작 열", number("manual-col", 3, 3, step=1)),
                ],
                id="manual-fields",
                className="two-columns",
                style={"display": "none"},
            ),
            dcc.Upload(
                id="source-upload",
                children=html.Div(
                    [
                        html.Strong("Excel 파일 선택"),
                        html.Small("끌어놓기 또는 클릭 · .xls / .xlsx"),
                    ]
                ),
                multiple=False,
                accept=".xls,.xlsx",
                max_size=50 * 1024 * 1024,
                className="upload",
            ),
            html.Div(
                "선택된 파일 없음", id="source-file-label", className="file-label"
            ),
            button("선택 파일 지우기", "clear-upload"),
            html.P(
                "미국 모드는 파일을 선택하지 않으면 제공된 자료를 사용합니다.",
                className="sidebar-help",
            ),
            button("데이터 불러오기", "load-source", True),
            button("작업 초기화", "reset-workspace"),
            html.Div(
                [
                    html.Span("●", className="status-dot"),
                    " Python 분석 엔진 · Plotly Dash",
                ],
                className="sidebar-footer",
            ),
        ],
        className="sidebar",
    )
    editing = html.Div(
        [
            card(
                "산업 편집",
                [
                    html.Div(
                        [
                            field(
                                "새 산업 코드",
                                dcc.Input(
                                    id="new-code", type="text", placeholder="예: 6000"
                                ),
                            ),
                            field(
                                "새 산업 이름",
                                dcc.Input(
                                    id="new-name", type="text", placeholder="예: TMT"
                                ),
                            ),
                            button("산업 추가", "insert-sector"),
                        ],
                        className="form-row",
                    ),
                    html.Div(
                        [
                            field(
                                "출발 산업 코드",
                                dcc.Input(
                                    id="from-code", type="text", placeholder="from"
                                ),
                            ),
                            field(
                                "대상 산업 코드",
                                dcc.Input(id="to-code", type="text", placeholder="to"),
                            ),
                            field(
                                "이동 비율", number("transfer-ratio", 0.0, 0, 1, 0.001)
                            ),
                            button("값 옮기기", "transfer-sector"),
                        ],
                        className="form-row",
                    ),
                    html.Div(
                        [
                            button("0인 행·열 삭제", "remove-zero"),
                            button("음수 값 절반으로", "reduce-negative"),
                            button("경제지표 계산", "run-analysis", True),
                        ],
                        className="button-row",
                    ),
                ],
                "총거래표와 국산거래표에 같은 편집을 적용합니다.",
            ),
            card(
                "일괄 편집",
                [
                    dcc.Upload(
                        id="batch-upload",
                        children=html.Div(
                            [
                                html.Strong("비율표 Excel / ZIP 선택"),
                                html.Small(
                                    "from · to · to_name · alpha 또는 연도별 비율표"
                                ),
                            ]
                        ),
                        multiple=False,
                        accept=".xls,.xlsx,.zip",
                        max_size=50 * 1024 * 1024,
                        className="upload compact",
                    ),
                    html.Div(id="batch-file-label", className="file-label"),
                    html.Div(
                        [
                            field(
                                "비율 적용 연도",
                                dcc.Dropdown(
                                    id="batch-year",
                                    options=[],
                                    value=None,
                                    placeholder="미리보기에서 연도 탐색",
                                ),
                            ),
                            field(
                                "대상 코드", dcc.Input(id="batch-code", value="6000")
                            ),
                            field("대상 이름", dcc.Input(id="batch-name", value="TMT")),
                        ],
                        className="three-columns",
                    ),
                    html.Div(
                        [
                            button("미리보기 생성", "preview-batch"),
                            button("일괄 적용", "apply-batch"),
                        ],
                        className="button-row",
                    ),
                    html.Div(id="batch-summary", className="hint"),
                    grid("batch-grid", 220),
                ],
            ),
            card(
                "현재 편집 중인 표",
                [
                    dcc.Input(
                        id="editor-search",
                        placeholder="표 안에서 검색",
                        type="search",
                        debounce=True,
                    ),
                    grid("editor-grid"),
                ],
            ),
        ],
        id="pane-edit",
        className="pane",
    )
    economic = html.Div(
        [
            card(
                "경제지표",
                [
                    html.Div(id="analysis-summary", className="hint"),
                    field(
                        "강조할 산업",
                        dcc.Dropdown(
                            id="highlight",
                            options=[],
                            value=None,
                            multi=True,
                            placeholder="차트에 강조할 산업을 선택하세요",
                        ),
                    ),
                    html.Div(
                        [graph("fl-bl"), graph("gdp-chart")],
                        className="two-columns charts",
                    ),
                ],
            ),
            card(
                "계산 결과 표",
                [
                    field(
                        "결과 선택",
                        dcc.Dropdown(
                            id="result-table", options=[], value=None, clearable=False
                        ),
                    ),
                    dcc.Input(
                        id="result-search",
                        placeholder="결과에서 검색",
                        type="search",
                        debounce=True,
                    ),
                    grid("result-grid"),
                ],
            ),
        ],
        id="pane-economic",
        className="pane",
        style={"display": "none"},
    )
    network = html.Div(
        [
            card(
                "네트워크 추출",
                [
                    field(
                        "추출 방식",
                        dcc.RadioItems(
                            id="network-method",
                            options=[
                                {"label": " Method A · 임계값", "value": "A"},
                                {"label": " Method B · 급수 전개", "value": "B"},
                            ],
                            value="A",
                            inline=True,
                        ),
                    ),
                    html.Div(
                        [
                            field("임계값", number("threshold", 0.0, 0, step=0.001)),
                            field(
                                "ε · 원소 제거 기준",
                                number("epsilon", 0.0001, 0.000000000001, step=0.00001),
                            ),
                            field(
                                "δ · 연결 변화율",
                                number("delta", 0.01, 0.000000000001, step=0.001),
                            ),
                            field("최대 반복", number("max-iter", 100, 1, 500, 1)),
                        ],
                        className="four-columns",
                    ),
                    html.P(
                        "Method A는 값 > 임계값인 연결을 선택합니다. Method B는 기존 규약대로 L을 사용하며, 수렴은 연결 개수의 안정화를 뜻합니다.",
                        className="hint",
                    ),
                    button("네트워크 추출", "run-network", True),
                    html.Div(id="network-summary", className="hint"),
                    html.Div(
                        [graph("threshold-chart"), graph("series-chart")],
                        className="two-columns charts",
                    ),
                ],
            ),
            card(
                "산업 네트워크와 중심성",
                [
                    dcc.RadioItems(
                        id="network-kind",
                        options=[
                            {"label": " 가중치 네트워크", "value": "weighted"},
                            {"label": " 이진 네트워크", "value": "binary"},
                        ],
                        value="weighted",
                        inline=True,
                    ),
                    graph("network-chart"),
                    html.P(
                        "연결 방향은 열 산업 j → 행 산업 i입니다. 연결이 많으면 화면에는 가중치 상위 1,200개만 표시하며 모든 연결은 결과 파일에 포함됩니다.",
                        className="hint",
                    ),
                    html.Div(
                        [graph("hits-chart"), graph("holes-chart")],
                        className="two-columns charts",
                    ),
                    field(
                        "중심성 표",
                        dcc.Dropdown(
                            id="centrality-table",
                            options=[
                                {"label": label, "value": name}
                                for name, label in [
                                    ("degree", "Degree"),
                                    ("betweenness", "Betweenness"),
                                    ("closeness", "Closeness"),
                                    ("eigenvector", "Eigenvector"),
                                    ("hits", "Hub · Authority"),
                                    ("structural_holes", "Constraint · Efficiency"),
                                ]
                            ],
                            value="degree",
                            clearable=False,
                        ),
                    ),
                    grid("centrality-grid", 350),
                ],
            ),
        ],
        id="pane-network",
        className="pane",
        style={"display": "none"},
    )
    export = html.Div(
        [
            card(
                "분석 결과 저장",
                [
                    html.P(
                        "원본·편집본·경제지표·현재 네트워크를 함께 저장합니다.",
                        className="hint",
                    ),
                    button("전체 결과 ZIP 다운로드", "download-zip", True),
                    field(
                        "개별 결과",
                        dcc.Dropdown(
                            id="export-table", options=[], value=None, clearable=False
                        ),
                    ),
                    button("선택 결과 CSV 다운로드", "download-csv"),
                ],
            ),
            card(
                "일본 산업연관표 원자료",
                [
                    field(
                        "원자료 선택",
                        dcc.Dropdown(
                            id="raw-resource",
                            options=resources,
                            value=resources[0]["value"] if resources else None,
                            clearable=False,
                        ),
                    ),
                    button("원자료 다운로드", "download-raw"),
                ],
            ),
            card("편집 이력", [html.Pre("편집 이력이 없습니다.", id="edit-log")]),
        ],
        id="pane-export",
        className="pane",
        style={"display": "none"},
    )
    main = html.Main(
        [
            html.Header(
                [
                    html.Div(
                        [
                            html.Div("INPUT–OUTPUT ANALYSIS", className="eyebrow"),
                            html.H1("산업연관 분석 워크벤치"),
                            html.P(
                                "데이터를 불러오고, 산업을 편집하고, 연결 구조를 탐색하세요."
                            ),
                        ]
                    ),
                    html.Span("DASH EDITION", className="edition"),
                ],
                className="page-header",
            ),
            html.Div(
                "원자료를 불러오면 분석을 시작할 수 있습니다.",
                id="source-summary",
                className="source-summary",
            ),
            html.Div(id="metrics", className="metrics"),
            html.Div(id="notice", role="status", **{"aria-live": "polite"}),
            dcc.Tabs(
                id="navigation",
                value="edit",
                className="navigation",
                children=[
                    dcc.Tab(label=label, value=value)
                    for value, label in [
                        ("edit", "01  데이터 · 편집"),
                        ("economic", "02  경제지표"),
                        ("network", "03  네트워크"),
                        ("export", "04  내보내기"),
                    ]
                ],
            ),
            editing,
            economic,
            network,
            export,
        ],
        className="main",
    )
    return html.Div(
        [
            dcc.Loading(
                [
                    dcc.Store(id="workspace", data=pointer, storage_type="memory"),
                    html.Div(id="busy-status"),
                ],
                type="circle",
                fullscreen=True,
            ),
            dcc.Download(id="file-download"),
            sidebar,
            main,
        ],
        className="app-shell",
    )
