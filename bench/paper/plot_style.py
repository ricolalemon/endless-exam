"""Shared visual specification for the paper's full-width scientific figures.

Export a fixed 5.5-inch canvas, matching the ICLR text width. Do not crop with
bbox_inches='tight': that silently changes the final scale of text and markers.
"""
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from publication_data import COLORS, REGISTRY
import visual_theme as T

WIDTH = 5.5
LABEL = 8.2
TITLE = 8.2
TICK = 7.2
LEGEND = 7.0
NOTE = 6.6
LINE = 1.2
MARKER = 3.7
CAP = 2.2
INK = T.INK
GRID = T.GRID
BOUND = {"color": INK, "linestyle": ":", "linewidth": 1.35, "zorder": 1}
REFERENCE = {"color": INK, "linestyle": (0, (5, 2.5)), "linewidth": 1.1, "zorder": 1}
EXPERT = {"color": T.MUTED, "linestyle": (0, (4, 2, 1, 2)), "linewidth": 1.1, "zorder": 1}
METRICS = {"published": T.OCHRE, "stand_in": T.PRIMARY, "valid": T.PRIMARY,
           "raw_search": T.NEUTRAL, "retained_search": T.MUTED, "best_model": T.OCHRE}
MARKERS = {"qwen4": "v", "qwen9": ">", "qwen35": "^", "qwen38": "s",
           "luna_medium": "o", "luna_high": "o", "deepseek_low": "P", "deepseek_high": "P",
           "fable": "h", "fable_high": "h", "astra_medium": "D", "astra_high": "D", "opus": "*"}
OPUS_COLOR = T.OPUS_COLOR
EFFORT_LINES = {"low": "-", "medium": "-", "high": (0, (4, 1.8)), "xhigh": (0, (4, 1.5, 1, 1.5))}


def apply():
    plt.rcParams.update({"font.family": "DejaVu Sans", "mathtext.fontset": "dejavusans",
        "font.size": LABEL, "axes.labelsize": LABEL, "axes.titlesize": TITLE,
        "axes.titleweight": "normal", "axes.titlepad": 6, "axes.labelpad": 3,
        "xtick.labelsize": TICK, "ytick.labelsize": TICK, "legend.fontsize": LEGEND,
        "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": T.AXIS,
        "xtick.color": T.AXIS, "ytick.color": T.AXIS, "axes.linewidth": .65,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.major.size": 2.8, "ytick.major.size": 2.8,
        "xtick.major.width": .65, "ytick.major.width": .65,
        "lines.linewidth": LINE, "lines.markersize": MARKER, "lines.markeredgewidth": .8,
        "grid.color": GRID, "grid.linewidth": .55, "grid.alpha": 1,
        "axes.axisbelow": True, "legend.frameon": False, "legend.handlelength": 2.1,
        "legend.columnspacing": 1.3, "legend.handletextpad": .55,
        "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.facecolor": "white"})


def color(sid): return OPUS_COLOR if sid == "opus" else COLORS[sid]


def style(sid):
    effort = REGISTRY[sid][2].split()[-1]
    return {"color": color(sid), "marker": MARKERS[sid], "linestyle": EFFORT_LINES.get(effort, "-"),
            "linewidth": LINE, "markersize": MARKER, "zorder": 3}


def config_style(model, config):
    base = config.split("#")[0]
    sid = next((sid for sid, s in REGISTRY.items() if s[1] == model and base in s[3:5]), None)
    if sid is None:
        sid = next(sid for sid, s in REGISTRY.items() if s[1] == model)
    return style(sid)


def reference_handles(expert=False):
    pairs = [(Line2D([], [], **REFERENCE), "Reference"),
             (Line2D([], [], **BOUND), "Proven bound")]
    if expert: pairs.append((Line2D([], [], **EXPERT), "Baseline"))
    return pairs


def legend(fig, handles, labels, ncol=3, y=.01):
    return fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.5, y),
                      ncol=ncol, fontsize=LEGEND, frameon=False)


def save(fig, name):
    """Keep exact physical width and reject clipped labels before writing."""
    assert abs(fig.get_figwidth() - WIDTH) < 1e-6
    fig.canvas.draw()
    bbox = fig.get_tightbbox(fig.canvas.get_renderer())
    if bbox.x0 < -.025 or bbox.y0 < -.025 or bbox.x1 > WIDTH + .025 or bbox.y1 > fig.get_figheight() + .025:
        raise ValueError(f"Figure labels exceed fixed canvas: {name}: {bbox.bounds}")
    out = Path(__file__).resolve().parent / "figs"
    out.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(out / f"{name}.{ext}", dpi=220, facecolor="white")
    plt.close(fig)
    print("wrote", name)
