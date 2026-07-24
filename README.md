# 산업연관데이터 DashBoard (KDasHboard)

산업연관표(Input–Output table)를 입력받아 부문을 편집하고, Leontief 역행렬과
전·후방 연쇄효과(FL/BL)를 계산하며, 산업 네트워크를 추출·분석하는 한국어
Streamlit 대시보드.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

`.devcontainer/` 는 requirements 자동 설치 후 8501 포트로 앱을 띄우도록 구성돼 있다.

## 회귀 테스트

백엔드 수치 동작이 보존됐는지 확인하는 회귀 테스트가 있다(실제 한국 통합중분류
표를 한 번 돌려 38개 산출물의 digest 를 baseline 과 비교):

```bash
python tests/regression_oracle.py           # baseline(tests/golden.json) 생성/갱신
python tests/regression_oracle.py --check    # baseline 과 비교, 다르면 비정상 종료
```

코드를 고친 뒤 `--check` 가 통과하면 백엔드 결과가 바뀌지 않은 것이다.

## 구조

| 파일/패키지 | 역할 |
|---|---|
| `app.py` | 전체 UI 흐름(`main()`). `st.session_state` 키로 단계가 순차적으로 열린다. |
| `iolib/` | 백엔드 패키지(로딩·편집·Leontief·네트워크·다운로드). 아래 표 참조. |
| `functions.py` | 하위호환 shim. `from functions import *` 가 `iolib` 를 그대로 재노출. |
| `preprocessing.py` | 모드별 업로드 파싱(한국/일본/수동/US BEA). |
| `bea_io_download.py` | BEA API 로 미국 IO 데이터 내려받기. |
| `tests/` | 회귀 오라클(`regression_oracle.py`)과 baseline(`golden.json`). |

### `iolib` 패키지 모듈

| 모듈 | 담당 |
|---|---|
| `iolib/loading.py` | 엑셀 로딩, 서브매트릭스 추출, 중간수요 경계(`mid_ID_idx`) 탐지 |
| `iolib/batch_upload.py` | 엑셀/ZIP 일괄편집 파일 파싱·미리보기 (한글 파일명 복구 포함) |
| `iolib/editing.py` | 부문 편집 연산(추가/이전/0삭제/음수보정)과 재생(`replay_edit_ops_on_df`) |
| `iolib/leontief.py` | 투입계수행렬·Leontief 역행렬·행렬 전처리·표 생성 |
| `iolib/network.py` | 네트워크 추출(Method A/B)·중심성·구조적 공백(Kim) 지표 |
| `iolib/download.py` | Streamlit 다운로드 버튼(CSV/ZIP) |

`new.py` 는 대시보드와 무관한 일회성 Selenium 스크레이퍼다. `app.py` 에 연결하지 말 것.

## 모드 → I/O 표 레이아웃

| 모드 | `first_idx` | 비고 |
|---|---|---|
| Korea(2010~2020) | (6, 2) | |
| Japan(2000~2020) | (6, 2) | |
| Korea(1990~2005) | (5, 2) | `df` 마지막 행 제거 |
| Manual | 0 | |
| US(BEA Summary) | (6, 2) | 연도 선택, 산업×산업 정사각 블록 추출 |
| US(BEA Detail) | (6, 2) | 벤치마크년(2007/2012/2017) |

업로더는 2-시트 워크북(시트0=전체표, 시트1=국내표)을 기대한다. 편집은 두 시트에
병렬로 적용된다.
