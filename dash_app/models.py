"""브라우저에 보내지 않는 사용자별 분석 상태."""

from dataclasses import dataclass, field
from iolib.session import EditingSession
from iolib.analysis import AnalysisResult
from iolib.network import ThresholdResult, SeriesResult
from iolib.network_analysis import NetworkResult


@dataclass(frozen=True)
class BatchPreview:
    records: list[dict]
    metadata: dict
    signature: tuple
    summaries: list[str]


@dataclass(frozen=True)
class Workspace:
    revision: int = 0
    editor: EditingSession | None = None
    analysis: AnalysisResult | None = None
    threshold: ThresholdResult | None = None
    series: SeriesResult | None = None
    network: NetworkResult | None = None
    network_frames: dict = field(default_factory=dict)
    network_settings: tuple | None = None
    batch: BatchPreview | None = None
    source_name: str = ""
    mode: str = ""
    year: int | None = None
