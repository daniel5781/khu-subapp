"""계산 결과를 Figure로 변환하는 선택적 matplotlib 어댑터."""

from matplotlib.figure import Figure


def plot_threshold(result):
    fig = Figure(figsize=(10, 7))
    ax = fig.subplots()
    ax.plot(result.thresholds, result.survival, label="Survival Ratio")
    ax.set(xlabel="Threshold", ylabel="Survival Ratio", title="Threshold Optimization")
    ax.axvline(
        result.distance_threshold, color="gray", linestyle="--", label="Distance Min"
    )
    ax.axvline(result.threshold, color="red", label=f"Final: {result.threshold:.4f}")
    if len(result.slope_changes):
        other = ax.twinx()
        other.plot(
            result.slope_thresholds, result.slope_changes, color="orange", alpha=0.4
        )
        other.set_ylabel("Slope Change Rate")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_series(info):
    fig = Figure(figsize=(10, 6))
    ax = fig.subplots()
    ax.plot(info["iterations"], info["densities"], marker="s", label="Edge count")
    ax.set(xlabel="Iteration", ylabel="Edge count", title="Leontief Series Expansion")
    other = ax.twinx()
    other.plot(
        info["iterations"], info["ratios"], color="red", marker="o", linestyle="--"
    )
    other.axhline(info["delta"], color="gray", linestyle="-.")
    other.set_ylabel("Change Ratio")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig
