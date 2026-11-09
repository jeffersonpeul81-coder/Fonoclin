"""Sistema de Audiometria Ocupacional — interface Streamlit.

Executar localmente:  streamlit run app.py
"""
import hmac
import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

import db
from classificacao import (ACEITAVEL, FREQS_VA, SUGESTIVO, avaliar_orelha, br,
                           sugerir_parecer)
from db import Audiometria, Empresa, Paciente
from relatorio import gerar_pdf

st.set_page_config(page_title="Audiometria Ocupacional", page_icon="🦻", layout="wide")

TIPOS = ["Admissional", "Periódico", "Demissional", "Mudança de função",
         "Retorno ao trabalho", "Mudança de riscos ocupacionais", "Monitoração pontual",
         "Outros"]
MEATO = ["Sem alterações", "Obstrução parcial por cerume", "Obstrução total por cerume",
         "Otorreia / secreção", "Outra alteração"]
SEXOS = ["", "Feminino", "Masculino"]
ss = st.session_state


@st.cache_resource
def _inicializar():
    db.init_db()
    return True


_inicializar()


# ------------------------------------------------------------------ utilidades
def ini(chave, valor):
    if chave not in ss:
        ss[chave] = valor


def fmt_data(d):
    return d.strftime("%d/%m/%Y") if d else ""


def ir_para(pagina, **extras):
    ss["ir_pagina"] = pagina
    for k, v in extras.items():
        ss[k] = v


def autenticado() -> bool:
    try:
        senha = st.secrets["APP_PASSWORD"]
    except Exception:
        senha = None
    if not senha:
        st.sidebar.warning("Modo local sem senha. Defina APP_PASSWORD nos *secrets* "
                           "antes de publicar.")
        return True
    if ss.get("auth"):
        return True
    st.title("🦻 Audiometria Ocupacional")
    with st.form("login"):
        pw = st.text_input("Senha de acesso", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            if hmac.compare_digest(pw.encode(), str(senha).encode()):
                ss["auth"] = True
                st.rerun()
            st.error("Senha incorreta.")
    return False


def df_orelha(o: dict) -> pd.DataFrame:
    o = o or {}
    linhas = []
    for f in FREQS_VA:
        k = str(f)
        linhas.append({
            "Frequência (Hz)": f,
            "VA (dB)": (o.get("va") or {}).get(k),
            "VA mascarada": bool((o.get("va_mask") or {}).get(k)),
            "Sem resposta": bool((o.get("va_sr") or {}).get(k)),
            "VO (dB)": (o.get("vo") or {}).get(k),
            "VO mascarada": bool((o.get("vo_mask") or {}).get(k)),
        })
    df = pd.DataFrame(linhas)
    for c in ("VA (dB)", "VO (dB)"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def df_para_orelha(df: pd.DataFrame) -> dict:
    o = {"va": {}, "va_mask": {}, "va_sr": {}, "vo": {}, "vo_mask": {}}
    for _, r in df.iterrows():
        f = str(int(r["Frequência (Hz)"]))
        if pd.notna(r["VA (dB)"]):
            o["va"][f] = int(r["VA (dB)"])
            if r["VA mascarada"]:
                o["va_mask"][f] = True
            if r["Sem resposta"]:
                o["va_sr"][f] = True
        if pd.notna(r["VO (dB)"]):
            o["vo"][f] = int(r["VO (dB)"])
            if r["VO mascarada"]:
                o["vo_mask"][f] = True
    return o


COLS_EDITOR = {
    "Frequência (Hz)": st.column_config.NumberColumn(disabled=True, format="%d"),
    "VA (dB)": st.column_config.NumberColumn(min_value=-10, max_value=120, step=5, format="%d"),
    "VA mascarada": st.column_config.CheckboxColumn(),
    "Sem resposta": st.column_config.CheckboxColumn(help="Sem resposta na intensidade máxima"),
    "VO (dB)": st.column_config.NumberColumn(min_value=-10, max_value=80, step=5, format="%d",
                                             help="Via óssea (normalmente 500 a 4.000 Hz)"),
    "VO mascarada": st.column_config.CheckboxColumn(),
}


def pdf_bytes(exame_id: int) -> bytes:
    return gerar_pdf(db.exame_completo(exame_id), db.get_profissional())


def nome_arquivo(ex) -> str:
    nome = "".join(c if c.isalnum() else "_" for c in ex.paciente.nome)[:40]
    return f"Audiometria_{nome}_{ex.data_exame:%Y-%m-%d}.pdf"


# ------------------------------------------------------------------ páginas
def pagina_exame():
    edit_id = ss.get("edit_id")
    exame = db.exame_completo(edit_id) if edit_id else None

    # aviso + download do último exame salvo
    if ss.get("ultimo_exame") and not exame:
        ult = db.exame_completo(ss["ultimo_exame"])
        if ult:
            c1, c2 = st.columns([3, 1])
            c1.success(f"Exame de **{ult.paciente.nome}** ({fmt_data(ult.data_exame)}) salvo.")
            c2.download_button("📄 Baixar laudo (PDF)", pdf_bytes(ult.id), nome_arquivo(ult),
                               "application/pdf", width="stretch")

    st.header("✏️ Editar audiometria" if exame else "➕ Nova audiometria")
    if exame:
        st.caption(f"Editando exame de {exame.paciente.nome} — {fmt_data(exame.data_exame)}")
        if st.button("← Cancelar edição"):
            ss.pop("edit_id", None)
            st.rerun()

    prof = db.get_profissional()

    # ---- paciente
    empresas = db.listar_empresas()
    if not empresas:
        st.info("Cadastre primeiro uma empresa (menu **Empresas**).")
        return
    if exame:
        paciente = exame.paciente
    else:
        c1, c2 = st.columns(2)
        mapa_emp = {e.id: e for e in empresas}
        emp_id = c1.selectbox("Empresa", [None] + list(mapa_emp),
                              format_func=lambda i: "Todas" if i is None else mapa_emp[i].razao_social)
        pacs = {p.id: p for p in db.buscar_pacientes(empresa_id=emp_id)}
        opcoes = [None] + list(pacs)
        pac_id = c2.selectbox(
            "Funcionário / paciente", opcoes,
            index=opcoes.index(ss["novo_pac"]) if ss.get("novo_pac") in pacs else 0,
            format_func=lambda i: "— selecione —" if i is None else
            f"{pacs[i].nome}  ·  {pacs[i].empresa.razao_social if pacs[i].empresa else 's/ empresa'}")
        with st.expander("Cadastrar novo funcionário"):
            form_paciente(None, empresa_padrao=emp_id)
        if not pac_id:
            return
        paciente = pacs[pac_id]

    k = f"e{exame.id}_" if exame else f"n{ss.get('form_n', 0)}_p{paciente.id}_"

    # valores iniciais
    ini(k + "data", exame.data_exame if exame else date.today())
    ini(k + "tipo", exame.tipo_exame if exame else "Periódico")
    ini(k + "emp", exame.empresa_id if exame else paciente.empresa_id)
    ini(k + "funcao", exame.funcao if exame else paciente.funcao)
    ini(k + "setor", exame.setor if exame else paciente.setor)
    ini(k + "repouso", exame.repouso_horas if exame else "14")
    ini(k + "m_od", exame.meatoscopia_od if exame else MEATO[0])
    ini(k + "m_oe", exame.meatoscopia_oe if exame else MEATO[0])
    ini(k + "aud", exame.audiometro if exame else prof.audiometro)
    ini(k + "calib", exame.data_calibracao if exame else prof.data_calibracao)
    ini(k + "anam", exame.anamnese if exame else "")
    ini(k + "ref", exame.referencial if exame else not db.exames_do_paciente(paciente.id))
    ini(k + "parecer", exame.parecer if exame else "")
    logo = exame.logoaudiometria if exame else {}
    for campo in ("lrf", "iprf", "iprf_int", "ldv"):
        for s in ("OD", "OE"):
            ini(f"{k}{campo}_{s}", str(logo.get(f"{campo}_{s}", "") or ""))

    st.subheader("Dados da avaliação")
    c = st.columns(4)
    c[0].date_input("Data do exame", key=k + "data", format="DD/MM/YYYY")
    c[1].selectbox("Tipo de exame", TIPOS, key=k + "tipo")
    ids_emp = [e.id for e in empresas]
    if ss[k + "emp"] not in ids_emp:
        ss[k + "emp"] = ids_emp[0]
    c[2].selectbox("Empresa (neste exame)", ids_emp, key=k + "emp",
                   format_func=lambda i: next(e.razao_social for e in empresas if e.id == i))
    c[3].text_input("Repouso auditivo (horas)", key=k + "repouso")
    c = st.columns(4)
    c[0].text_input("Função", key=k + "funcao")
    c[1].text_input("Setor", key=k + "setor")
    c[2].selectbox("Meatoscopia OD", MEATO, key=k + "m_od")
    c[3].selectbox("Meatoscopia OE", MEATO, key=k + "m_oe")
    c = st.columns([2, 1, 1])
    c[0].text_input("Audiômetro (marca/modelo)", key=k + "aud")
    c[1].date_input("Data da calibração", key=k + "calib", format="DD/MM/YYYY")
    c[2].checkbox("Exame de referência", key=k + "ref",
                  help="Marque no admissional ou quando este exame passar a ser a nova "
                       "referência (após desencadeamento/agravamento confirmado).")
    st.text_area("Anamnese / queixas / exposição", key=k + "anam", height=80)

    # ---- limiares
    st.subheader("Limiares tonais (dB NA)")
    lim_ini = exame.limiares if exame else {}
    c_od, c_oe = st.columns(2)
    with c_od:
        st.markdown("<span style='color:#C62828;font-weight:700'>● Orelha direita (OD)</span>",
                    unsafe_allow_html=True)
        df_od = st.data_editor(df_orelha(lim_ini.get("OD")), key=k + "ed_od", hide_index=True,
                               num_rows="fixed", column_config=COLS_EDITOR,
                               width="stretch")
    with c_oe:
        st.markdown("<span style='color:#1565C0;font-weight:700'>✕ Orelha esquerda (OE)</span>",
                    unsafe_allow_html=True)
        df_oe = st.data_editor(df_orelha(lim_ini.get("OE")), key=k + "ed_oe", hide_index=True,
                               num_rows="fixed", column_config=COLS_EDITOR,
                               width="stretch")
    limiares = {"OD": df_para_orelha(df_od), "OE": df_para_orelha(df_oe)}

    fora_passo = [f"{s} {f} Hz" for s in ("OD", "OE") for via in ("va", "vo")
                  for f, v in limiares[s][via].items() if v % 5]
    if fora_passo:
        st.warning("Limiares fora do passo de 5 dB: " + ", ".join(fora_passo))

    # ---- logoaudiometria
    with st.expander("Logoaudiometria (opcional)", expanded=bool(logo)):
        for s in ("OD", "OE"):
            c = st.columns(5)
            c[0].markdown(f"**{s}**")
            c[1].text_input("LRF (dB NA)", key=f"{k}lrf_{s}")
            c[2].text_input("IPRF (%)", key=f"{k}iprf_{s}")
            c[3].text_input("Intensidade IPRF", key=f"{k}iprf_int_{s}")
            c[4].text_input("LDV (dB NA)", key=f"{k}ldv_{s}")

    # ---- análise e parecer
    st.subheader("Análise e parecer")
    ref = db.exame_referencia(paciente.id, ss[k + "data"], exame.id if exame else None)
    usar_ref = ref if (ref and not ss[k + "ref"]) else None
    c = st.columns(2)
    for col, s in zip(c, ("OD", "OE")):
        r = avaliar_orelha(limiares[s])
        icone = "🟢" if r["classe"] == ACEITAVEL else ("🔴" if r["classe"] == SUGESTIVO else "🟡")
        col.markdown(f"**{s}:** {icone} {r['classe']}  \n"
                     f"Média 0,5/1/2 kHz: **{br(r['media_tritonal']) if r['media_tritonal'] is not None else '—'}** · "
                     f"Média 3/4/6 kHz: **{br(r['media_altas']) if r['media_altas'] is not None else '—'}** · "
                     f"{r['grau']}")
    if usar_ref:
        st.caption(f"Exame de referência para comparação: {usar_ref.tipo_exame} de "
                   f"{fmt_data(usar_ref.data_exame)}")
    sugestao = sugerir_parecer(limiares, usar_ref.limiares if usar_ref else None,
                               fmt_data(usar_ref.data_exame) if usar_ref else None)
    ss[k + "sugestao"] = sugestao
    if sugestao:
        st.info("**Sugestão automática (revise antes de usar):**\n\n" + sugestao)

        def _usar():
            ss[k + "parecer"] = ss[k + "sugestao"]

        st.button("Usar sugestão no parecer", on_click=_usar)
    st.text_area("Parecer fonoaudiológico", key=k + "parecer", height=140)

    # ---- salvar
    if st.button("💾 Salvar exame", type="primary"):
        if not limiares["OD"]["va"] and not limiares["OE"]["va"]:
            st.error("Informe ao menos os limiares de via aérea.")
            return
        logo_dados = {}
        for campo in ("lrf", "iprf", "iprf_int", "ldv"):
            for s in ("OD", "OE"):
                v = ss[f"{k}{campo}_{s}"].strip()
                if v:
                    logo_dados[f"{campo}_{s}"] = v
        novo = Audiometria(
            id=exame.id if exame else None,
            paciente_id=paciente.id, empresa_id=ss[k + "emp"],
            data_exame=ss[k + "data"], tipo_exame=ss[k + "tipo"],
            funcao=ss[k + "funcao"], setor=ss[k + "setor"], repouso_horas=ss[k + "repouso"],
            meatoscopia_od=ss[k + "m_od"], meatoscopia_oe=ss[k + "m_oe"],
            audiometro=ss[k + "aud"], data_calibracao=ss[k + "calib"],
            anamnese=ss[k + "anam"], referencial=ss[k + "ref"],
            limiares_json=json.dumps(limiares), logo_json=json.dumps(logo_dados),
            parecer=ss[k + "parecer"],
            criado_em=exame.criado_em if exame else datetime.now(),
        )
        salvo = db.salvar(novo)
        ss["ultimo_exame"] = salvo.id
        ss.pop("edit_id", None)
        ss.pop("novo_pac", None)
        ss["form_n"] = ss.get("form_n", 0) + 1
        if exame:
            ss["ir_pagina"] = "Pacientes e histórico"
            ss["pac_sel"] = paciente.id
        st.rerun()


def form_paciente(pac: Paciente | None, empresa_padrao=None):
    empresas = db.listar_empresas()
    k = f"pac{pac.id if pac else 'novo'}_"
    with st.form(k + "form", clear_on_submit=pac is None):
        c = st.columns([3, 2, 2])
        nome = c[0].text_input("Nome completo*", value=pac.nome if pac else "")
        cpf = c[1].text_input("CPF", value=pac.cpf if pac else "")
        rg = c[2].text_input("RG", value=pac.rg if pac else "")
        c = st.columns(4)
        nasc = c[0].date_input("Nascimento", value=pac.data_nascimento if pac else None,
                               min_value=date(1930, 1, 1), max_value=date.today(),
                               format="DD/MM/YYYY")
        sexo = c[1].selectbox("Sexo", SEXOS, index=SEXOS.index(pac.sexo) if pac and pac.sexo in SEXOS else 0)
        ids = [e.id for e in empresas]
        padrao = pac.empresa_id if pac else empresa_padrao
        emp = c[2].selectbox("Empresa atual", [None] + ids,
                             index=([None] + ids).index(padrao) if padrao in ids else 0,
                             format_func=lambda i: "—" if i is None else
                             next(e.razao_social for e in empresas if e.id == i))
        adm = c[3].date_input("Admissão", value=pac.data_admissao if pac else None,
                              min_value=date(1950, 1, 1), format="DD/MM/YYYY")
        c = st.columns(2)
        funcao = c[0].text_input("Função", value=pac.funcao if pac else "")
        setor = c[1].text_input("Setor", value=pac.setor if pac else "")
        obs = st.text_area("Observações", value=pac.observacoes if pac else "", height=68)
        if st.form_submit_button("Salvar funcionário", type="primary"):
            if not nome.strip():
                st.error("Informe o nome.")
                return
            p = db.salvar(Paciente(id=pac.id if pac else None, nome=nome.strip().upper(),
                                   cpf=cpf, rg=rg, data_nascimento=nasc, sexo=sexo,
                                   empresa_id=emp, funcao=funcao, setor=setor,
                                   data_admissao=adm, observacoes=obs))
            ss["novo_pac"] = p.id
            st.success("Funcionário salvo.")
            st.rerun()


def pagina_pacientes():
    st.header("👥 Funcionários e histórico")
    c = st.columns([2, 2])
    busca = c[0].text_input("Buscar por nome")
    empresas = db.listar_empresas()
    mapa_emp = {e.id: e for e in empresas}
    emp = c[1].selectbox("Empresa", [None] + list(mapa_emp),
                         format_func=lambda i: "Todas" if i is None else mapa_emp[i].razao_social)
    pacs = db.buscar_pacientes(busca, emp)
    st.caption(f"{len(pacs)} funcionário(s) encontrado(s)")
    if not pacs:
        with st.expander("Cadastrar novo funcionário", expanded=True):
            form_paciente(None, empresa_padrao=emp)
        return
    ids = [p.id for p in pacs]
    idx = ids.index(ss["pac_sel"]) if ss.get("pac_sel") in ids else 0
    mapa = {p.id: p for p in pacs}
    pac = mapa[st.selectbox("Selecione", ids, index=idx,
                            format_func=lambda i: f"{mapa[i].nome}  ·  CPF {mapa[i].cpf or '—'}  ·  "
                                                  f"{mapa[i].empresa.razao_social if mapa[i].empresa else 's/ empresa'}")]
    ss["pac_sel"] = pac.id

    aba_hist, aba_dados, aba_novo = st.tabs(["Histórico de exames", "Dados cadastrais",
                                             "Novo funcionário"])
    with aba_hist:
        exames = db.exames_do_paciente(pac.id)
        st.button("➕ Nova audiometria para este funcionário",
                  on_click=ir_para, args=("Nova audiometria",), kwargs={"novo_pac": pac.id})
        if not exames:
            st.info("Nenhum exame registrado.")
        if len(exames) > 1:
            evol = pd.DataFrame([{
                "Data": e.data_exame,
                "OD (média 3/4/6 kHz)": avaliar_orelha(e.limiares.get("OD", {}))["media_altas"],
                "OE (média 3/4/6 kHz)": avaliar_orelha(e.limiares.get("OE", {}))["media_altas"],
            } for e in exames]).set_index("Data").sort_index()
            st.markdown("**Evolução — média de 3, 4 e 6 kHz (dB NA)**")
            st.line_chart(evol, color=["#C62828", "#1565C0"], height=200)
        for e in exames:
            r_od = avaliar_orelha(e.limiares.get("OD", {}))["classe"]
            r_oe = avaliar_orelha(e.limiares.get("OE", {}))["classe"]
            titulo = (f"{fmt_data(e.data_exame)} — {e.tipo_exame}"
                      f"{' ⭐ referência' if e.referencial else ''} — "
                      f"{e.empresa.razao_social if e.empresa else ''}")
            with st.expander(titulo):
                st.markdown(f"**OD:** {r_od}  \n**OE:** {r_oe}")
                if e.parecer:
                    st.markdown("**Parecer:** " + e.parecer.replace("\n", "  \n"))
                c = st.columns(3)
                if c[0].button("📄 Gerar laudo", key=f"pdf{e.id}"):
                    ss[f"pdfbytes{e.id}"] = pdf_bytes(e.id)
                if ss.get(f"pdfbytes{e.id}"):
                    c[0].download_button("⬇️ Baixar PDF", ss[f"pdfbytes{e.id}"],
                                         nome_arquivo(db.exame_completo(e.id)),
                                         "application/pdf", key=f"dl{e.id}")
                c[1].button("✏️ Editar", key=f"ed{e.id}", on_click=ir_para,
                            args=("Nova audiometria",), kwargs={"edit_id": e.id})
                conf = c[2].checkbox("Confirmar exclusão", key=f"cf{e.id}")
                if c[2].button("🗑️ Excluir", key=f"del{e.id}", disabled=not conf):
                    db.excluir(Audiometria, e.id)
                    st.rerun()
    with aba_dados:
        form_paciente(pac)
        st.divider()
        conf = st.checkbox("Quero excluir este funcionário e TODOS os seus exames")
        if st.button("Excluir funcionário", disabled=not conf):
            db.excluir(Paciente, pac.id)
            ss.pop("pac_sel", None)
            st.rerun()
    with aba_novo:
        form_paciente(None, empresa_padrao=emp)


def pagina_empresas():
    st.header("🏭 Empresas")
    empresas = db.listar_empresas()
    if empresas:
        st.dataframe(pd.DataFrame([{"Razão social": e.razao_social, "CNPJ": e.cnpj,
                                    "Cidade/UF": e.cidade_uf, "Telefone": e.telefone,
                                    "Contato": e.contato, "Ativa": e.ativa} for e in empresas]),
                     hide_index=True, width="stretch")
    mapa = {e.id: e for e in empresas}
    sel_id = st.selectbox("Editar ou cadastrar", [None] + list(mapa),
                          format_func=lambda i: "➕ Nova empresa" if i is None else mapa[i].razao_social)
    sel = mapa.get(sel_id)
    with st.form(f"emp{sel.id if sel else 'nova'}", clear_on_submit=sel is None):
        c = st.columns([3, 1])
        rs = c[0].text_input("Razão social*", value=sel.razao_social if sel else "")
        cnpj = c[1].text_input("CNPJ", value=sel.cnpj if sel else "")
        c = st.columns([3, 1])
        end = c[0].text_input("Endereço", value=sel.endereco if sel else "")
        cid = c[1].text_input("Cidade/UF", value=sel.cidade_uf if sel else "")
        c = st.columns([1, 2, 1])
        tel = c[0].text_input("Telefone", value=sel.telefone if sel else "")
        cont = c[1].text_input("Contato (RH/SESMT)", value=sel.contato if sel else "")
        ativa = c[2].checkbox("Ativa", value=sel.ativa if sel else True)
        if st.form_submit_button("Salvar empresa", type="primary"):
            if not rs.strip():
                st.error("Informe a razão social.")
            else:
                db.salvar(Empresa(id=sel.id if sel else None, razao_social=rs.strip().upper(),
                                  cnpj=cnpj, endereco=end, cidade_uf=cid, telefone=tel,
                                  contato=cont, ativa=ativa))
                st.success("Empresa salva.")
                st.rerun()


def pagina_config():
    st.header("⚙️ Configurações")
    p = db.get_profissional()
    with st.form("prof"):
        st.subheader("Dados da profissional (cabeçalho do laudo)")
        c = st.columns([2, 1])
        nome = c[0].text_input("Nome da fonoaudióloga", value=p.nome)
        crfa = c[1].text_input("CRFa (ex.: 8617-PR)", value=p.crfa)
        c = st.columns([2, 1])
        clinica = c[0].text_input("Nome da clínica / consultório", value=p.clinica)
        doc = c[1].text_input("CNPJ ou CPF", value=p.cnpj_cpf)
        c = st.columns([3, 1])
        end = c[0].text_input("Endereço", value=p.endereco)
        cid = c[1].text_input("Cidade/UF", value=p.cidade_uf)
        c = st.columns(2)
        tel = c[0].text_input("Telefone", value=p.telefone)
        email = c[1].text_input("E-mail", value=p.email)
        st.subheader("Equipamento padrão")
        c = st.columns([2, 1])
        aud = c[0].text_input("Audiômetro (marca/modelo)", value=p.audiometro)
        cal = c[1].date_input("Última calibração", value=p.data_calibracao, format="DD/MM/YYYY")
        st.subheader("Imagens")
        c = st.columns(2)
        logo = c[0].file_uploader("Logotipo (PNG/JPG)", type=["png", "jpg", "jpeg"])
        assin = c[1].file_uploader("Assinatura digitalizada (opcional, PNG)", type=["png", "jpg", "jpeg"])
        if st.form_submit_button("Salvar configurações", type="primary"):
            p.nome, p.crfa, p.clinica, p.cnpj_cpf = nome, crfa, clinica, doc
            p.endereco, p.cidade_uf, p.telefone, p.email = end, cid, tel, email
            p.audiometro, p.data_calibracao = aud, cal
            if logo:
                p.logo = logo.getvalue()
            if assin:
                p.assinatura = assin.getvalue()
            db.salvar(p)
            st.success("Configurações salvas.")
            st.rerun()
    c = st.columns(2)
    if p.logo:
        c[0].image(p.logo, caption="Logotipo atual", width=180)
        if c[0].button("Remover logotipo"):
            p.logo = None
            db.salvar(p)
            st.rerun()
    if p.assinatura:
        c[1].image(p.assinatura, caption="Assinatura atual", width=180)
        if c[1].button("Remover assinatura"):
            p.assinatura = None
            db.salvar(p)
            st.rerun()

    st.divider()
    st.subheader("Cópia de segurança")
    st.caption("Baixe periodicamente um backup completo dos cadastros e exames (JSON).")
    if st.button("Preparar backup"):
        ss["backup"] = json.dumps(db.exportar_tudo(), ensure_ascii=False, indent=1)
    if ss.get("backup"):
        st.download_button("⬇️ Baixar backup", ss["backup"],
                           f"backup_audiometria_{date.today():%Y-%m-%d}.json", "application/json")


# ------------------------------------------------------------------ roteamento
if autenticado():
    with st.sidebar:
        st.title("🦻 Audiometria")
        st.caption("Ocupacional · NR-7")
        ini("pagina", "Nova audiometria")
        if "ir_pagina" in ss:
            ss["pagina"] = ss.pop("ir_pagina")
        st.radio("Menu", ["Nova audiometria", "Pacientes e histórico", "Empresas",
                          "Configurações"], key="pagina", label_visibility="collapsed")
        if ss.get("auth") and st.button("Sair"):
            ss.clear()
            st.rerun()
    {"Nova audiometria": pagina_exame,
     "Pacientes e histórico": pagina_pacientes,
     "Empresas": pagina_empresas,
     "Configurações": pagina_config}[ss["pagina"]]()
