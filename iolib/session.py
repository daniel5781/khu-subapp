"""총거래·국산거래표에 편집을 원자적으로 적용하는 UI 독립 서비스."""

from copy import deepcopy
from dataclasses import dataclass, field, replace
from .models import LoadResult, ModeParams
from .editing import (
    insert_row_and_col,
    transfer_to_new_sector,
    remove_zero_series,
    reduce_negative_values,
    apply_batch_edit,
    replay_edit_ops_on_df,
)
from .analysis import validate_sector_alignment, analyze_tables


@dataclass(frozen=True)
class EditingSession:
    original: LoadResult
    params: ModeParams
    total: object
    domestic: object
    mid: tuple[int, int]
    mid_local: tuple[int, int]
    names: dict = field(default_factory=dict)
    operations: tuple = ()
    logs: tuple[str, ...] = ()

    @classmethod
    def from_loaded(cls, loaded, params):
        validate_sector_alignment(
            loaded.df,
            loaded.df_local,
            params.first_idx,
            loaded.mid_ID_idx,
            loaded.mid_ID_idx_local,
        )
        return cls(
            loaded,
            params,
            loaded.df.copy(),
            loaded.df_local.copy(),
            loaded.mid_ID_idx,
            loaded.mid_ID_idx_local,
        )

    def apply(self, operation):
        operation = deepcopy(operation)
        if operation["type"] == "remove_zero":
            *_, positions = remove_zero_series(
                self.total, self.params.first_idx, self.mid
            )
            operation["remove_positions"] = positions
        if operation["type"] == "reduce_negative":
            # mid는 합계 경계이며 exclusive slice가 이미 합계를 제외한다.
            operation.setdefault("use_minus_one_mid", False)
        kwargs = dict(
            first_idx=self.params.first_idx,
            number_of_label=self.params.number_of_label,
            insert_row_and_col_fn=insert_row_and_col,
            transfer_to_new_sector_fn=transfer_to_new_sector,
            remove_zero_series_fn=remove_zero_series,
            reduce_negative_values_fn=reduce_negative_values,
            batch_apply_fn=apply_batch_edit,
            copy_ids=True,
        )
        total, mid, names, log = replay_edit_ops_on_df(
            self.total, self.mid, self.names, [operation], **kwargs
        )
        domestic, mid_local, _, _ = replay_edit_ops_on_df(
            self.domestic, self.mid_local, self.names, [operation], **kwargs
        )
        validate_sector_alignment(
            total, domestic, self.params.first_idx, mid, mid_local
        )
        return replace(
            self,
            total=total,
            domestic=domestic,
            mid=mid,
            mid_local=mid_local,
            names=names,
            operations=self.operations + (operation,),
            logs=self.logs + (log,),
        )

    def analyze(self):
        return analyze_tables(
            self.total,
            self.domestic,
            first_idx=self.params.first_idx,
            mid=self.mid,
            mid_local=self.mid_local,
        )
