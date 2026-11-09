"""Critérios de interpretação — NR-7, Anexo II (Portaria SEPRT nº 6.734/2020)
e grau de perda pela classificação de Lloyd & Kaplan (1978).

ATENÇÃO: as sugestões são apenas auxiliares. O parecer final é sempre do(a)
fonoaudiólogo(a) / médico(a) responsável.
"""
from statistics import mean

FREQS_VA = [250, 500, 1000, 2000, 3000, 4000, 6000, 8000]
FREQS_VO = [500, 1000, 2000, 3000, 4000]
ALTAS = (3000, 4000, 6000)
TRITONAL = (500, 1000, 2000)

ACEITAVEL = "Limiares auditivos dentro dos limites aceitáveis"
SUGESTIVO = "Limiares auditivos sugestivos de PAINPSE"
NAO_SUGESTIVO = "Limiares auditivos não sugestivos de PAINPSE"


def _va(orelha: dict) -> dict:
    """{freq:int -> limiar:int} apenas com valores válidos (ignora 'sem resposta' como 120)."""
    va = orelha.get("va", {}) or {}
    sr = orelha.get("va_sr", {}) or {}
    out = {}
    for f in FREQS_VA:
        v = va.get(str(f))
        if v is not None:
            out[f] = 125 if sr.get(str(f)) else int(v)
    return out


def _vo(orelha: dict) -> dict:
    vo = orelha.get("vo", {}) or {}
    return {int(f): int(v) for f, v in vo.items() if v is not None}


def br(n) -> str:
    """Número no padrão brasileiro (vírgula decimal)."""
    return f"{n:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def media(limiares: dict, freqs) -> float | None:
    vals = [limiares[f] for f in freqs if f in limiares]
    return round(mean(vals), 1) if len(vals) == len(freqs) else None


def grau_lloyd_kaplan(m: float | None) -> str:
    if m is None:
        return "—"
    if m <= 25:
        return "Audição normal"
    if m <= 40:
        return "Perda auditiva de grau leve"
    if m <= 55:
        return "Perda auditiva de grau moderado"
    if m <= 70:
        return "Perda auditiva de grau moderadamente severo"
    if m <= 90:
        return "Perda auditiva de grau severo"
    return "Perda auditiva de grau profundo"


def avaliar_orelha(orelha: dict) -> dict:
    va = _va(orelha)
    vo = _vo(orelha)
    res = {
        "classe": "Não avaliada",
        "media_tritonal": media(va, TRITONAL),
        "media_altas": media(va, ALTAS),
        "grau": "—",
        "observacao": "",
    }
    if not va:
        return res
    res["grau"] = grau_lloyd_kaplan(res["media_tritonal"])

    if all(v <= 25 for v in va.values()):
        res["classe"] = ACEITAVEL
        return res

    altas = [va[f] for f in ALTAS if f in va]
    outras = [va[f] for f in va if f not in ALTAS]
    perfil_altas = bool(altas) and max(altas) > 25 and max(altas) > max(outras or [-20])

    # gap aéreo-ósseo > 10 dB em 3 ou 4 kHz indica componente condutivo
    gaps = [va[f] - vo[f] for f in (3000, 4000) if f in va and f in vo]
    condutivo = any(g > 10 for g in gaps)

    if perfil_altas and not condutivo:
        res["classe"] = SUGESTIVO
    else:
        res["classe"] = NAO_SUGESTIVO
        if perfil_altas and condutivo:
            res["observacao"] = ("Configuração em frequências altas com gap aéreo-ósseo "
                                 "> 10 dB — avaliar componente condutivo/misto.")
    return res


def comparar(ref: dict, atual: dict) -> str:
    """Comparação sequencial x referencial (NR-7, Anexo II, itens 5.1 e 5.2)."""
    va_r, va_a = _va(ref), _va(atual)
    if not va_r or not va_a:
        return ""
    ref_aceitavel = all(v <= 25 for v in va_r.values())
    cls_atual = avaliar_orelha(atual)["classe"]

    def piora(freqs):
        return [f for f in freqs if f in va_r and f in va_a and va_a[f] - va_r[f] >= 15]

    m_altas_r, m_altas_a = media(va_r, ALTAS), media(va_a, ALTAS)
    dif_altas = (m_altas_a - m_altas_r) if None not in (m_altas_r, m_altas_a) else None

    if ref_aceitavel:
        if cls_atual != SUGESTIVO:
            return "Sem sinais de desencadeamento em relação ao exame de referência."
        criterios = []
        if dif_altas is not None and dif_altas >= 10:
            criterios.append(f"piora de {br(dif_altas)} dB na média de 3, 4 e 6 kHz")
        p = piora(ALTAS)
        if p:
            criterios.append("piora ≥ 15 dB em " + ", ".join(f"{f // 1000} kHz" for f in p))
        if criterios:
            return "Sugestivo de DESENCADEAMENTO de PAINPSE (" + "; ".join(criterios) + ")."
        return "Sem sinais de desencadeamento em relação ao exame de referência."

    # referência já com perda sugestiva -> avaliar agravamento
    m_tri_r, m_tri_a = media(va_r, TRITONAL), media(va_a, TRITONAL)
    criterios = []
    if None not in (m_tri_r, m_tri_a) and m_tri_a - m_tri_r >= 10:
        criterios.append(f"piora de {br(m_tri_a - m_tri_r)} dB na média de 0,5, 1 e 2 kHz")
    if dif_altas is not None and dif_altas >= 10:
        criterios.append(f"piora de {br(dif_altas)} dB na média de 3, 4 e 6 kHz")
    p = piora([500, 1000, 2000, 3000, 4000, 6000])
    if p:
        criterios.append("piora ≥ 15 dB em " + ", ".join(
            f"{f / 1000:g} kHz".replace(".", ",") for f in p))
    if criterios:
        return "Sugestivo de AGRAVAMENTO de PAINPSE (" + "; ".join(criterios) + ")."
    return "Sem sinais de agravamento em relação ao exame de referência."


def sugerir_parecer(limiares: dict, ref_limiares: dict | None = None,
                    ref_data: str | None = None) -> str:
    linhas = []
    for sigla, nome in (("OD", "Orelha direita"), ("OE", "Orelha esquerda")):
        ore = limiares.get(sigla, {})
        r = avaliar_orelha(ore)
        if r["classe"] == "Não avaliada":
            continue
        txt = f"{nome}: {r['classe']}"
        if r["classe"] != ACEITAVEL and r["grau"] not in ("—", "Audição normal"):
            txt += f" — {r['grau'].lower()} (média 0,5/1/2 kHz = {br(r['media_tritonal'])} dB NA)"
        txt += "."
        if r["observacao"]:
            txt += " " + r["observacao"]
        if ref_limiares and ref_limiares.get(sigla):
            comp = comparar(ref_limiares[sigla], ore)
            if comp:
                txt += f" Comparação com exame de referência ({ref_data}): {comp}"
        linhas.append(txt)
    if not linhas:
        return ""
    linhas.append("Interpretação conforme NR-7, Anexo II (Portaria SEPRT nº 6.734/2020).")
    return "\n".join(linhas)
