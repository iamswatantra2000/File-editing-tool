"""
Chart generation via matplotlib.
All charts are rendered to a temporary PNG and the path is returned
so docx_ops can embed it as an image.
"""

import tempfile
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")  # no display needed
import matplotlib.pyplot as plt


def _tmp_png(prefix: str = "chart") -> Path:
    fd, path = tempfile.mkstemp(suffix=".png", prefix=f"{prefix}_")
    import os; os.close(fd)
    return Path(path)


def pie_chart(
    labels: List[str],
    values: List[float],
    title: str = "",
    width_in: float = 5.0,
    height_in: float = 4.0,
) -> Path:
    """Render a pie chart and return the path to the temporary PNG."""
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=140)
    ax.axis("equal")
    if title:
        ax.set_title(title)
    path = _tmp_png("pie")
    fig.savefig(str(path), bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def bar_chart(
    labels: List[str],
    values: List[float],
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    width_in: float = 6.0,
    height_in: float = 4.0,
) -> Path:
    """Render a bar chart and return the path to the temporary PNG."""
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.bar(labels, values)
    if title:
        ax.set_title(title)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    path = _tmp_png("bar")
    fig.savefig(str(path), bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


CHART_BUILDERS: Dict[str, callable] = {
    "pie": pie_chart,
    "bar": bar_chart,
}


def build_chart(chart_type: str, **kwargs) -> Path:
    builder = CHART_BUILDERS.get(chart_type)
    if builder is None:
        raise ValueError(f"Unknown chart type: {chart_type!r}. Choose from {list(CHART_BUILDERS)}")
    return builder(**kwargs)
