# 산업연관데이터 DashBoard (KDasHboard)

한국·일본·미국 산업연관표를 읽고 산업을 편집한 뒤 Leontief 역행렬,
전·후방 연쇄효과, GDP·부가가치 유발효과와 산업 네트워크를 분석합니다.
한국어 Streamlit 화면과 독립 Python 라이브러리 `iolib`로 구성됩니다.

## 실행

Python 3.10 이상을 사용합니다.

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
| `app.py` | 기존 실행 명령을 유지하는 진입점 |
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
| `iolib/exports.py`, `plots.py` | CSV/ZIP 직렬화, 선택적 Figure 어댑터 |
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
목적산업(기본 `6000 / TMT`)과 미리보기를 확인한 뒤 `일괄 적용` → `전체 적용`을 누릅니다.
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
python -m pip install -e '.[dashboard,dev]'
ruff check .
python -m unittest discover -s tests -v
python tests/regression_oracle.py --check
python -m build
```

단위·통합 테스트는 정확한 행렬 항등식, 거래량 보존, 편집 원자성, 고립 그래프,
시트 선택과 Streamlit AppTest의 실제 폼 제출·분석·상태 전환을 검사합니다.
저장소에 포함된 미국 두 분류의 모든 가용 연도와 일본 5개 연도도 끝까지 계산합니다.
기존 회귀 오라클은 실제 한국 2020 표의 38개 digest를 비교합니다.
`tests/golden.json`은 의도한 수치 규약 변경이 있을 때만 검토 후 갱신합니다.

CI는 Python 3.10·3.13에서 검사와 sdist/wheel 빌드를 수행하도록 구성돼 있습니다.
GitHub에 반영한 뒤 원격 실행 결과를 확인할 수 있습니다.

`dist/khu_subapp-0.1.0-py3-none-any.whl`을 별도 환경에 설치할 수 있습니다.
패키지 배포·PyPI 업로드는 별도로 수행합니다.

`new.py`는 대시보드와 무관한 일회성 스크레이퍼입니다. `bea_io_download.py` 등
데이터 생성 스크립트도 앱 실행과 독립적이며, BEA 도구 의존성은 `.[bea]`로 설치합니다.
