# 산업연관데이터 DashBoard (KDasHboard)

한국·일본·미국 산업연관표를 읽고 산업을 편집한 뒤 Leontief 역행렬,
전·후방 연쇄효과, GDP·부가가치 유발효과와 산업 네트워크를 분석합니다.
독립 Python 라이브러리 `iolib`와 두 가지 한국어 화면으로 구성됩니다.
**Dash 버전**은 Plotly 대화형 차트와 AG Grid를 사용하고, 기존 Streamlit 버전도 함께 제공합니다.

## Dash 버전 실행

Python 3.10 이상을 사용합니다. 저장소 폴더에서 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e '.[dash]'
khu-dash --port 8050
```

브라우저에서 `http://127.0.0.1:8050`을 엽니다. `python app_dash.py` 또는
`python -m dash_app`도 같은 앱을 실행합니다. `pip install -r requirements-dash.txt`로도
설치할 수 있습니다. Dash 버전은 Streamlit·matplotlib를 설치하거나 불러오지 않습니다.

1. 왼쪽에서 국가·표 형식과 파일을 선택하고 **데이터 불러오기**를 누릅니다.
   미국 모드는 연도 선택 후 제공된 워크북으로 시작할 수 있습니다.
2. **데이터 · 편집**에서 산업 추가·비율 이동·음수 보정·일괄 편집을 적용합니다.
   일괄 편집은 **미리보기 생성 → 일괄 적용** 순서입니다. 연도 목록만 나타나면
   적용 연도를 선택한 뒤 미리보기를 다시 생성합니다.
3. **경제지표 계산**을 누르고 **경제지표**에서 FL/BL·GDP 차트와 결과 표를 확인합니다.
4. **네트워크**에서 Method A/B 설정 후 **네트워크 추출**을 누릅니다.
   가중·이진 네트워크, HITS·구조적 공백 차트와 6종 중심성 표를 탐색합니다.
5. **내보내기**에서 현재 자료를 CSV·ZIP으로 저장하거나 일본 원자료를 받습니다.

차트는 확대·이동·값 확인과 PNG 저장을 지원합니다. 표는 검색·정렬·필터·페이지
이동을 지원하며, 편집 작업은 위의 폼에서 적용합니다. 그래프가 크면 연결선 상위
1,200개만 화면에 표시합니다. 중심성 계산과 다운로드에는 전체 연결을 사용합니다.

사용자별 작업은 서버의 임시 디스크 저장소에 보관합니다. 새로고침·새 탭은 새
작업을 시작하며, 2시간 동안 접근하지 않은 작업은 만료됩니다. 종료 전에 필요한
결과를 내려받으세요. 기본 CLI는 종료 시 임시 폴더를 정리합니다. `--cache-dir`로
지정한 폴더는 종료 시 보존하며, 캐시 크기는 기본 512MB로 제한됩니다.
동시 편집 요청은 버전을 검사해 먼저 끝난 요청 하나만 반영합니다.
원자료 설정을 바꾸면 편집과 계산을 초기화하고, 편집하면 계산 결과를 지웁니다.
네트워크 설정을 바꾸면 네트워크를 다시 추출해야 합니다.

```bash
khu-dash --data-dir /path/to/khu-subapp-main --port 8050
# 필요할 때 작업 저장 위치도 지정
khu-dash --data-dir /path/to/data --cache-dir /path/to/cache
```

Waitress 서버는 기본적으로 로컬 주소 `127.0.0.1`에서 실행됩니다. 상태 확인 경로는
`/healthz`입니다. 파일별 업로드 한도는 50MB입니다.

## 기존 Streamlit 버전 실행

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e '.[dashboard,dev]'
streamlit run app.py
```

기존 `pip install -r requirements.txt`도 지원합니다.
설치 후에는 어느 디렉터리에서든 다음 명령으로 실행할 수 있습니다.

```bash
khu-subapp --data-dir /path/to/khu-subapp-main --port 8501
```

`--data-dir` 또는 환경 변수 `KHU_SUBAPP_DATA_DIR`은 미국 워크북과
`일본_산업연관표_연도별_자료/`가 있는 폴더입니다. 소스에서 실행할 때 기본값은
저장소 루트입니다. **대용량 원자료는 wheel에 포함하지 않습니다.**
한국·일본 파일 업로드는 원자료 폴더 설정 없이도 사용할 수 있습니다.
Streamlit Cloud는 `requirements.txt`와 한글 폰트용 `packages.txt`를 사용합니다.

## Python 라이브러리로 사용

패키지의 `dash`·`dashboard`·`plots` 의존성은 각각 선택해서 설치합니다.
UI 없이 계산만 사용하려면 `python -m pip install .`로 설치합니다.
`import iolib`는 Streamlit·matplotlib를 불러오지 않습니다.

```python
from iolib import load_workbook, get_mode_params, EditingSession, analyze_network

mode = 'Korea(2010~2020)'
loaded = load_workbook('산업연관표.xlsx', mode)
editor = EditingSession.from_loaded(loaded, get_mode_params(mode))
editor = editor.apply({'type': 'insert_sector', 'code': '6000', 'name': 'TMT'})
# 실제 표의 산업 코드를 사용합니다.
# editor = editor.apply({'type': 'transfer', 'from': 'C09', 'to': '6000', 'alpha': 0.2})
analysis = editor.analyze()
print(analysis.statistics['GDP_total'])

matrix = analysis.total.inverse.copy()
matrix[matrix <= 0.01] = 0
network = analyze_network(matrix, analysis.frames['leontief_inverse'])

from iolib.exports import make_zip_bytes
from pathlib import Path
Path('results.zip').write_bytes(make_zip_bytes({**analysis.frames, **network.frames}))
```

`EditingSession.apply()`는 새 편집 세션을 반환합니다. 총거래표와 국산거래표를
함께 갱신하며 한쪽이 실패하면 기존 세션은 바뀌지 않습니다.
`analyze()`는 편집을 재적용하지 않으므로 반복 실행해도 결과가 동일합니다.

## 모듈 구성

| 구성요소 | 책임 |
|---|---|
| `app_dash.py`, `dash_app/cli.py`, `app.py` | Dash·Streamlit 실행 진입점 |
| `dash_app/app.py`, `layout.py`, `assets/` | Dash 앱 팩토리, 화면 배치, 스타일 |
| `dash_app/callbacks.py`, `views.py` | 이벤트 연결, 저장된 상태의 화면 표시 |
| `dash_app/services.py`, `models.py`, `store.py` | 작업 흐름, 상태 계약, 사용자별 저장·동시성 제어 |
| `dash_app/uploads.py`, `tables.py`, `figures.py` | 업로드 검증, AG Grid 변환, Plotly 차트 |
| `dashboard/app.py` | 화면 구성요소의 실행 순서 |
| `dashboard/upload.py`, `editing.py` | 파일·모드 선택, 수동·일괄 편집 폼 |
| `dashboard/analysis.py`, `network.py` | 분석 결과와 네트워크 표시, UI 캐시 |
| `dashboard/state.py` | 파일·편집 변경 시 결과 무효화, 전체 다운로드 수집 |
| `dashboard/charts.py`, `tables.py`, `fonts.py` | 공통 차트, 혼합형 표 표시, 한글 폰트 |
| `dashboard/downloads.py`, `cli.py` | 다운로드 버튼·원자료, 설치 후 실행 명령 |
| `iolib/config.py`, `models.py` | 모드·데이터 위치 설정, 공통 데이터 계약 |
| `iolib/preprocessing.py`, `us_workbooks.py`, `loading.py` | 한국·일본·수동·미국 워크북 읽기와 표 경계 |
| `iolib/editing.py`, `batch_upload.py`, `session.py` | 편집 연산·검증·업로드, 두 표에 대한 원자적 편집 |
| `iolib/leontief.py`, `analysis.py` | 정규화·역행렬, FL/BL·GDP·부가가치 계산 |
| `iolib/network.py`, `network_analysis.py` | Method A/B 추출과 공통 네트워크 결과 조립 |
| `iolib/centrality.py`, `structural.py` | 중심성·HITS, 구조적 공백 지표 |
| `iolib/exports.py`, `resources.py`, `plots.py` | 공통 결과 수집·CSV/ZIP, 원자료, 선택적 Figure 어댑터 |
| `functions.py`, `preprocessing.py`, `iolib/download.py` | 기존 import/함수 호출의 호환 계층 |

`iolib` 계산 함수는 Streamlit 상태를 읽거나 화면을 그리지 않습니다.
캐시는 화면 계층에만 적용합니다. 계산 함수에 전달한 원표·행렬은 변경하지 않습니다.

## 입력 형식

| 모드 | 숫자 시작 위치 (0부터) | 내용 |
|---|---|---|
| `Korea(2010~2020)` | `(6, 2)` | 같은 한국은행 레이아웃의 최근 연도도 사용 가능 |
| `Japan(2000~2020)` | `(6, 2)` | 총거래+국산 또는 총거래+수입 시트 |
| `Korea(1990~2005)` | `(5, 2)` | 기존 구형 양식의 마지막 부가 행 제거 규약 유지 |
| `Manual` | 기본 `(6, 2)`, 화면에서 변경 | 코드·이름 라벨 2행/2열을 포함하는 같은 표 구조 |
| `US(Summary 2000~2024)` | `(6, 2)`로 변환 | BEA Use 중분류 71개 산업 |
| `US(Sector 2000~2024)` | `(6, 2)`로 변환 | BEA Use 대분류 15개 산업 |

한국은행 표는 시트 순서와 무관하게 **총거래표·국산거래표**를 이름으로 선택합니다.
수입거래표를 국산거래표로 대체하지 않습니다. 한국 표 이름이 없는 구형 파일은
기존 시트0=총거래, 시트1=국산 순서를 사용합니다.

일본 표는 국산 시트가 있으면 그대로 사용하고, 수입 시트만 있으면
중간거래 블록을 `총거래 − 수입`으로 변환합니다. 이름 없는 구형 일본 파일은
시트0=총거래, 시트1=수입 규약입니다. 수입 시트가 없는 1995년 단일 총거래 자료는
국산 분석에 사용할 수 없으며 화면에 필요한 시트를 안내합니다.

원표는 중간수요·중간투입 합계 경계가 있어야 하며, 총거래표의 마지막 두 행은
부가가치계·총투입계여야 합니다. `X`, `D`, `V` 등으로 이미 분해된 여러 시트는
이 입력 계약에 해당하지 않습니다. 잘못된 표, 산업 순서 불일치, 특이행렬은
설명과 함께 계산을 중단합니다.

미국 모드는 두 워크북에 공통으로 있는 연도만 표시합니다. 업로드 시 총거래표만
대체되고 국산표는 데이터 폴더의 해당 연도를 사용합니다. Used는 부가가치계,
Other는 별도 기타투입으로 분류하며 T018을 정규화 분모로 사용합니다.

## 편집과 연도별 TMT 비율

`Alpha 값 엑셀/ZIP 파일 업로드`에 다음 중 하나를 올립니다.

- `from`, `to`, `to_name`, `alpha` 열: `alpha`는 0~1, 출발 산업별 합은 1 이하입니다.
- 첫 열이 `대분류/년도`이고 이후 연도 열에 `20.380%(C09)` 형식으로 비율이 있는 표.

연도별 표는 원본 표의 연도를 우선 제안합니다. 연도를 찾지 못하면 선택하고,
목적산업(기본 `6000 / TMT`)과 미리보기를 확인한 뒤 일괄 적용합니다.
Streamlit에서는 이어서 `전체 적용`으로 경제지표를 계산합니다.
빈 셀과 연도 열 뒤 참고 계산은 제외합니다. `11` 같은 숫자코드는 `0011`처럼
앞에 0이 붙은 유일한 원본 코드에 대응합니다. 같은 비율의 중복 적용을 막습니다.

산업 내부 거래는 행 분배 후 갱신된 열을 분배하여 `P X Pᵀ`와 일치하게 처리합니다.
잘못된 비율·없는 코드·중복 코드가 있으면 일부만 적용하지 않습니다.
음수 보정은 마지막 산업도 포함하고 기존 규약대로 차이를 마지막 행에 반영합니다.

## 분석 규약

- `A = X / 총투입계`는 열 위치 기준입니다. `L = (I - A)⁻¹`에서 FL은 행합,
  BL은 열합을 각각 평균으로 나눕니다.
- 국산표도 총거래표의 총투입계로 정규화합니다. `v = 부가가치 / 총투입계`,
  `GDP = diag(v) L y`, `m_v = v L_domestic`입니다.
- Method A는 실제 적용과 같은 `값 > 임계값` 기준을 사용합니다. 대각·0 연결은
  생존율에서 제외하고 원래 고립된 산업은 따로 표시합니다.
- Method B 화면은 기존 분석과의 호환성을 위해 **L**의 거듭제곱 누적합을 사용합니다.
  수렴 표시는 **연결 개수의 안정화**이며 급수의 수학적 수렴을 뜻하지 않습니다.
  `extract_series_network(A, ...)`를 직접 호출하면 투입계수행렬 A도 사용할 수 있습니다.
- 그래프 방향은 기존 규약인 열 `j → 행 i`입니다. 가중 최단경로 중심성은 기존과
  동일하게 가중치를 거리로 해석합니다. 이진 지표는 HITS를 포함해 모두 단위 가중치입니다.
- 고립 노드의 constraint처럼 정의되지 않는 지표는 NaN으로 남습니다. 빈 연결·단일
  산업도 예외 없이 분석하며, 전체 ZIP에는 현재 원본·편집·경제지표·네트워크가 포함됩니다.

## 검증과 패키지 빌드

```bash
python -m pip install -e '.[dashboard,dash,dev]'
ruff check .
python -m unittest discover -s tests -v
python tests/regression_oracle.py --check
python -m build
```

단위·통합 테스트는 정확한 행렬 항등식, 거래량 보존, 편집 원자성, 고립 그래프,
시트 선택과 Streamlit AppTest의 실제 폼 제출·분석·상태 전환을 검사합니다.
Dash는 Flask 테스트 클라이언트로 실제 업로드·편집·분석·다운로드 콜백 요청,
콜백 의존성의 순환 여부, 사용자별 작업 격리와 동시 저장 충돌을 검사합니다.
Streamlit·matplotlib 없이 Dash 앱이 생성되는지도 확인합니다.
저장소에 포함된 미국 두 분류의 모든 가용 연도와 일본 5개 연도도 끝까지 계산합니다.
기존 회귀 오라클은 실제 한국 2020 표의 38개 digest를 비교합니다.
`tests/golden.json`은 의도한 수치 규약 변경이 있을 때만 검토 후 갱신합니다.

CI는 Python 3.10·3.13에서 검사와 sdist/wheel 빌드를 수행하도록 구성돼 있습니다.
GitHub에 반영한 뒤 원격 실행 결과를 확인할 수 있습니다.

`dist/khu_subapp-0.2.0-py3-none-any.whl`을 별도 환경에 설치할 수 있습니다.
패키지 배포·PyPI 업로드는 별도로 수행합니다.

`new.py`는 대시보드와 무관한 일회성 스크레이퍼입니다. `bea_io_download.py` 등
데이터 생성 스크립트도 앱 실행과 독립적이며, BEA 도구 의존성은 `.[bea]`로 설치합니다.
