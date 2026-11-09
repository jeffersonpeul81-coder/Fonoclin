"""Desenho dos audiogramas (OD e OE) com a simbologia padronizada
(Guia de Orientação CFFa/ASHA):
  OD: VA  O  | VA mascarada  △ | VO  <  | VO mascarada  [   (vermelho)
  OE: VA  X  | VA mascarada  □ | VO  >  | VO mascarada  ]   (azul)
  Sem resposta: seta para baixo junto ao símbolo.
"""
from io import BytesIO
from math import log2

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from classificacao import FREQS_VA  # noqa: E402

COR = {"OD": "#C62828", "OE": "#1565C0"}
ROTULOS = ["250", "500", "1k", "2k", "3k", "4k", "6k", "8k"]


def _x(f: int) -> float:
    return log2(f / 250)


def desenhar(sigla: str, orelha: dict, largura=4.3, altura=3.45) -> bytes:
    cor = COR[sigla]
    od = sigla == "OD"
    va = orelha.get("va", {}) or {}
    va_m = orelha.get("va_mask", {}) or {}
    va_sr = orelha.get("va_sr", {}) or {}
    vo = orelha.get("vo", {}) or {}
    vo_m = orelha.get("vo_mask", {}) or {}

    fig, ax = plt.subplots(figsize=(largura, altura), dpi=200)
    ax.set_xlim(-0.4, _x(8000) + 0.4)
    ax.set_ylim(120, -10)
    ax.set_xticks([_x(f) for f in FREQS_VA])
    ax.set_xticklabels(ROTULOS, fontsize=7)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("Frequência (Hz)", fontsize=7)
    ax.set_yticks(range(-10, 121, 10))
    ax.tick_params(axis="y", labelsize=7)
    ax.set_ylabel("Nível de audição (dB NA)", fontsize=7)
    ax.grid(True, color="#BDBDBD", linewidth=0.5)
    ax.axhspan(-10, 25, color="#E8F5E9", zorder=0)
    ax.axhline(25, color="#81C784", linewidth=0.8, linestyle="--", zorder=1)
    for f in (3000, 6000):  # meias oitavas tracejadas
        ax.axvline(_x(f), color="#BDBDBD", linewidth=0.5, linestyle=":")
    ax.set_title("Orelha Direita" if od else "Orelha Esquerda",
                 fontsize=9, color=cor, fontweight="bold", pad=18)

    # ---- via aérea
    xs, ys = [], []
    for f in FREQS_VA:
        v = va.get(str(f))
        if v is None:
            continue
        x, y = _x(f), float(v)
        mask = bool(va_m.get(str(f)))
        sr = bool(va_sr.get(str(f)))
        if od:
            mk = "^" if mask else "o"
        else:
            mk = "s" if mask else "x"
        if mk in ("x",):
            ax.plot(x, y, marker=mk, color=cor, markersize=7, mew=1.6, zorder=4)
        else:
            ax.plot(x, y, marker=mk, color=cor, markersize=7, mew=1.4,
                    markerfacecolor="white", zorder=4)
        if sr:
            dx = -0.18 if od else 0.18
            ax.annotate("", xy=(x + dx, y + 9), xytext=(x, y + 2),
                        arrowprops=dict(arrowstyle="-|>", color=cor, lw=1.1), zorder=4)
        else:
            xs.append(x)
            ys.append(y)
    if len(xs) > 1:
        ax.plot(xs, ys, color=cor, linewidth=1.3, zorder=3)

    # ---- via óssea
    for f, v in vo.items():
        if v is None:
            continue
        mask = bool(vo_m.get(str(f)))
        simb = ("[" if mask else "<") if od else ("]" if mask else ">")
        dx = -0.17 if od else 0.17
        ax.text(_x(int(f)) + dx, float(v), simb, color=cor, fontsize=11,
                ha="center", va="center", fontweight="bold", zorder=5)

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
