"""Emissão do laudo de audiometria ocupacional em PDF (A4)."""
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from audiograma import desenhar
from classificacao import FREQS_VA, avaliar_orelha, br

import os

import matplotlib
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# DejaVu acompanha o matplotlib -> funciona igual no Windows, Linux e Streamlit Cloud
_fdir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(_fdir, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(_fdir, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                              italic="DejaVu", boldItalic="DejaVu-Bold")
pdfmetrics.registerFont(TTFont("DejaVuSerif-Italic", os.path.join(_fdir, "DejaVuSerif-Italic.ttf")))
FR, FB, FI = "DejaVu", "DejaVu-Bold", "DejaVuSerif-Italic"

# Identidade visual FONOCLIN (laranja suave + cinza escuro)
LARANJA = colors.HexColor("#F4B183")   # faixas de seção
LARANJA_ESC = colors.HexColor("#E2704F")  # linha do cabeçalho
TEXTO = colors.HexColor("#3A3A3A")
AZUL = TEXTO  # compatibilidade
CINZA = colors.HexColor("#FDF1E8")     # fundo dos rótulos
BORDA = colors.HexColor("#E6CDBB")

st_tit = ParagraphStyle("tit", fontName=FB, fontSize=13, leading=15,
                        alignment=TA_CENTER, textColor=TEXTO)
st_sec = ParagraphStyle("sec", fontName=FB, fontSize=8.5, textColor=TEXTO)
st_txt = ParagraphStyle("txt", fontName=FR, fontSize=7.8, leading=9.6)
st_lbl = ParagraphStyle("lbl", parent=st_txt, fontName=FB)
st_par = ParagraphStyle("par", parent=st_txt, fontSize=8.3, leading=11, alignment=TA_JUSTIFY)
st_cab_nome = ParagraphStyle("cabn", fontName=FI, fontSize=15, leading=18,
                             textColor=TEXTO, alignment=TA_CENTER)
st_cab_sub = ParagraphStyle("cabs", fontName=FR, fontSize=9, leading=11,
                            textColor=TEXTO, alignment=TA_CENTER)
st_cab = ParagraphStyle("cab", parent=st_txt, fontSize=7.3, leading=9,
                        textColor=colors.HexColor("#666666"), alignment=TA_CENTER)
st_centro = ParagraphStyle("c", parent=st_txt, alignment=TA_CENTER)

LARG = A4[0] - 2.4 * cm


def _d(v) -> str:
    return v.strftime("%d/%m/%Y") if isinstance(v, date) else ""


def _idade(nasc: date | None, ref: date) -> str:
    if not nasc:
        return ""
    a = ref.year - nasc.year - ((ref.month, ref.day) < (nasc.month, nasc.day))
    return f"{a} anos"


def _secao(titulo: str):
    t = Table([[Paragraph(titulo, st_sec)]], colWidths=[LARG])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LARANJA),
                           ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def _grade(pares, colunas=4, w_lbl=2.3 * cm):
    """pares = [(rótulo, valor), ...] distribuídos em `colunas` pares por linha."""
    linhas, linha = [], []
    for rot, val in pares:
        linha += [Paragraph(rot, st_lbl), Paragraph(str(val or "—"), st_txt)]
        if len(linha) == colunas * 2:
            linhas.append(linha)
            linha = []
    if linha:
        linha += [""] * (colunas * 2 - len(linha))
        linhas.append(linha)
    w_val = (LARG - colunas * w_lbl) / colunas
    t = Table(linhas, colWidths=[w_lbl, w_val] * colunas)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ] + [("BACKGROUND", (i, 0), (i, -1), CINZA) for i in range(0, colunas * 2, 2)]))
    return t


def _fmt_limiar(orelha, via, f):
    v = (orelha.get(via) or {}).get(str(f))
    if v is None:
        return "—"
    txt = str(v)
    if via == "va" and (orelha.get("va_sr") or {}).get(str(f)):
        txt += "↓"
    if (orelha.get(f"{via}_mask") or {}).get(str(f)):
        txt += "*"
    return txt


def gerar_pdf(exame, profissional) -> bytes:
    pac = exame.paciente
    emp = exame.empresa
    lim = exame.limiares
    logo = exame.logoaudiometria
    buf = BytesIO()

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont(FR, 6.5)
        canvas.setFillColor(colors.grey)
        partes = [profissional.clinica or profissional.nome,
                  " – ".join(x for x in (profissional.endereco, profissional.cidade_uf) if x),
                  profissional.telefone, profissional.email]
        canvas.drawCentredString(A4[0] / 2, 0.8 * cm, " · ".join(p for p in partes if p))
        canvas.drawRightString(A4[0] - 1.2 * cm, 0.8 * cm, f"Pág. {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                            topMargin=1.0 * cm, bottomMargin=1.4 * cm,
                            title=f"Audiometria - {pac.nome}",
                            author=profissional.nome or "")
    el = []

    # ---------- cabeçalho
    info = [Paragraph(profissional.nome or profissional.clinica or "Fonoaudiologia", st_cab_nome)]
    sub = "Fonoaudióloga" + (f" – CRFa {profissional.crfa}" if profissional.crfa else "")
    info.append(Paragraph(sub, st_cab_sub))
    end = " – ".join(x for x in (profissional.endereco, profissional.cidade_uf) if x)
    cont = " · ".join(x for x in (profissional.telefone, profissional.email,
                                   profissional.cnpj_cpf) if x)
    if end or cont:
        info.append(Spacer(1, 2))
    if end:
        info.append(Paragraph(end, st_cab))
    if cont:
        info.append(Paragraph(cont, st_cab))

    if profissional.logo:
        img = ImageReader(BytesIO(profissional.logo))
        iw, ih = img.getSize()
        h = 1.9 * cm
        w = min(h * iw / ih, 4.2 * cm)
        h = w * ih / iw
        logo_img = Image(BytesIO(profissional.logo), width=w, height=h)
        cab = Table([[logo_img, info, ""]], colWidths=[4.4 * cm, LARG - 8.8 * cm, 4.4 * cm])
    else:
        cab = Table([[info]], colWidths=[LARG])
    cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LINEBELOW", (0, 0), (-1, 0), 1.2, LARANJA_ESC),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                             ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    titulo = Table([[Paragraph("AVALIAÇÃO AUDIOLÓGICA OCUPACIONAL", st_tit)]], colWidths=[LARG])
    titulo.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LARANJA),
                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    el += [cab, Spacer(1, 4), titulo, Spacer(1, 2),
           Paragraph(f"Exame <b>{exame.tipo_exame.upper()}</b> · realizado em "
                     f"{_d(exame.data_exame)}", st_centro), Spacer(1, 5)]

    # ---------- empresa
    el.append(_secao("DADOS DA EMPRESA"))
    el.append(_grade([
        ("Razão social", emp.razao_social if emp else ""),
        ("CNPJ", emp.cnpj if emp else ""),
        ("Endereço", " – ".join(x for x in ((emp.endereco if emp else ""),
                                           (emp.cidade_uf if emp else "")) if x)),
        ("Telefone", emp.telefone if emp else ""),
    ], colunas=2))
    el.append(Spacer(1, 4))

    # ---------- funcionário
    el.append(_secao("DADOS DO FUNCIONÁRIO"))
    el.append(_grade([
        ("Nome", pac.nome), ("CPF", pac.cpf),
        ("Nascimento", f"{_d(pac.data_nascimento)}  ({_idade(pac.data_nascimento, exame.data_exame)})"
         if pac.data_nascimento else ""),
        ("Sexo", pac.sexo),
        ("Função", exame.funcao or pac.funcao), ("Setor", exame.setor or pac.setor),
    ], colunas=2))
    el.append(Spacer(1, 4))

    # ---------- dados do exame
    el.append(_secao("DADOS DA AVALIAÇÃO"))
    el.append(_grade([
        ("Tipo de exame", exame.tipo_exame),
        ("Repouso auditivo", f"{exame.repouso_horas} h" if exame.repouso_horas else ""),
        ("Meatoscopia OD", exame.meatoscopia_od), ("Meatoscopia OE", exame.meatoscopia_oe),
        ("Audiômetro", exame.audiometro),
        ("Calibração", _d(exame.data_calibracao)),
    ], colunas=3, w_lbl=2.65 * cm))
    if exame.anamnese:
        t = Table([[Paragraph("<b>Anamnese / queixas:</b> " + exame.anamnese.replace("\n", "<br/>"),
                              st_txt)]], colWidths=[LARG])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, BORDA)]))
        el.append(t)
    el.append(Spacer(1, 5))

    # ---------- audiogramas
    w_img = LARG / 2 - 0.2 * cm
    h_img = w_img * 3.45 / 4.3
    w_img = w_img * 0.84
    h_img = h_img * 0.84
    img_od = Image(BytesIO(desenhar("OD", lim.get("OD", {}))), width=w_img, height=h_img)
    img_oe = Image(BytesIO(desenhar("OE", lim.get("OE", {}))), width=w_img, height=h_img)
    t = Table([[img_od, img_oe]], colWidths=[LARG / 2, LARG / 2])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                           ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    el.append(t)
    leg = ("<font color='#C62828'><b>OD:</b> O via aérea · △ VA mascarada · &lt; via óssea · "
           "[ VO mascarada</font> &nbsp;&nbsp; <font color='#1565C0'><b>OE:</b> X via aérea · "
           "□ VA mascarada · &gt; via óssea · ] VO mascarada</font> &nbsp;&nbsp; ↓ sem resposta")
    el.append(Paragraph(leg, ParagraphStyle("leg", parent=st_centro, fontSize=6.5)))
    el.append(Spacer(1, 4))

    # ---------- tabela de limiares
    cab_t = ["Hz"] + [f"{f:,}".replace(",", ".") for f in FREQS_VA] + \
        ["Média\n0,5-1-2k", "Média\n3-4-6k"]
    linhas = [cab_t]
    for sig in ("OD", "OE"):
        o = lim.get(sig, {})
        r = avaliar_orelha(o)
        linhas.append([f"{sig} – VA"] + [_fmt_limiar(o, "va", f) for f in FREQS_VA] +
                      [br(r["media_tritonal"]) if r["media_tritonal"] is not None else "—",
                       br(r["media_altas"]) if r["media_altas"] is not None else "—"])
        linhas.append([f"{sig} – VO"] + [_fmt_limiar(o, "vo", f) for f in FREQS_VA] + ["", ""])
    wc = (LARG - 2.0 * cm - 3.0 * cm) / len(FREQS_VA)
    t = Table(linhas, colWidths=[2.0 * cm] + [wc] * len(FREQS_VA) + [1.5 * cm, 1.5 * cm])
    estilo = [
        ("FONT", (0, 0), (-1, -1), FR, 7.3),
        ("FONT", (0, 0), (-1, 0), FB, 7),
        ("FONT", (0, 1), (0, -1), FB, 7.3),
        ("BACKGROUND", (0, 0), (-1, 0), CINZA),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDA),
        ("TEXTCOLOR", (0, 1), (-1, 2), colors.HexColor("#C62828")),
        ("TEXTCOLOR", (0, 3), (-1, 4), colors.HexColor("#1565C0")),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
    ]
    t.setStyle(TableStyle(estilo))
    el.append(t)
    el.append(Paragraph("Valores em dB NA. * = com mascaramento · ↓ = sem resposta na "
                        "intensidade máxima.", ParagraphStyle("n", parent=st_txt, fontSize=6.3)))
    el.append(Spacer(1, 4))

    # ---------- logoaudiometria
    if any(logo.get(k) for k in logo):
        lg = [["", "LRF (dB NA)", "IPRF (%)", "Intensidade IPRF (dB NA)", "LDV (dB NA)"]]
        for sig in ("OD", "OE"):
            lg.append([sig] + [str(logo.get(f"{c}_{sig}", "") or "—")
                               for c in ("lrf", "iprf", "iprf_int", "ldv")])
        t = Table(lg, colWidths=[2.0 * cm] + [(LARG - 2.0 * cm) / 4] * 4)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), FR, 7.3),
            ("FONT", (0, 0), (-1, 0), FB, 7.3),
            ("FONT", (0, 1), (0, -1), FB, 7.3),
            ("BACKGROUND", (0, 0), (-1, 0), CINZA),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), 0.4, BORDA),
            ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ]))
        el.append(_secao("LOGOAUDIOMETRIA"))
        el.append(t)
        el.append(Spacer(1, 4))

    # ---------- parecer
    el.append(_secao("PARECER FONOAUDIOLÓGICO"))
    par = Table([[Paragraph((exame.parecer or "—").replace("\n", "<br/>"), st_par)]],
                colWidths=[LARG])
    par.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, BORDA),
                             ("TOPPADDING", (0, 0), (-1, -1), 4),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    el.append(par)
    el.append(Spacer(1, 14))

    # ---------- assinaturas
    def bloco(nome, sub, img=None):
        conteudo = []
        if img:
            ir = ImageReader(BytesIO(img))
            iw, ih = ir.getSize()
            h = 1.1 * cm
            conteudo.append(Image(BytesIO(img), width=h * iw / ih, height=h))
        conteudo += [Paragraph("_" * 42, st_centro), Paragraph(f"<b>{nome}</b>", st_centro),
                     Paragraph(sub, st_centro)]
        return conteudo

    ass = Table([[bloco(profissional.nome or "Fonoaudióloga",
                        f"CRFa {profissional.crfa}" if profissional.crfa else "Fonoaudióloga",
                        profissional.assinatura),
                  bloco(pac.nome, "Funcionário(a)")]],
                colWidths=[LARG / 2, LARG / 2])
    ass.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    el.append(ass)

    doc.build(el, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()
