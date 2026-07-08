from __future__ import annotations

import base64
from datetime import date, timedelta
import html
from pathlib import Path

import streamlit as st

from web import services as svc
from web.db import LOGO_PATH, UPLOAD_DIR, init_db
from web.reports import (
    _linha_relatorio_carregamento,
    desenhar_relatorio_carregamentos,
    exportar_log_para_excel,
    gerar_relatorio_escala_cd,
    gerar_relatorio_folgas,
    gerar_relatorio_oficinas,
)


NAV_ITEMS = [
    "Carregamentos",
    "Escala (CD)",
    "Folgas",
    "Oficinas",
    "Rotas Semanais",
    "Caminhões",
    "Férias",
    "Colaboradores",
    "LOG",
]


@st.cache_data(ttl=3600, show_spinner=False)
def _data_uri(path: Path) -> str:
    if not path or not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    ext = path.suffix.lower().lstrip(".") or "png"
    return f"data:image/{ext};base64,{data}"


@st.cache_data(ttl=3600, show_spinner=False)
def _load_css() -> str:
    css_path = Path("web/static/css/app.css")
    css_text = ""
    if css_path.exists():
        css_text = css_path.read_text(encoding="utf-8")
    font_path = Path("web/static/fonts/Sora.ttf")
    if font_path.exists():
        font_data = base64.b64encode(font_path.read_bytes()).decode("ascii")
        css_text = css_text.replace(
            'url("/static/fonts/Sora.ttf")',
            f"url(data:font/ttf;base64,{font_data})",
        )
    return css_text


def _inject_css() -> None:
    css_text = _load_css()
    extra = """
    .stApp {
      background: radial-gradient(circle at 15% 10%, #edf2fb, transparent 45%),
        radial-gradient(circle at 90% 5%, #f8fafc, transparent 40%),
        linear-gradient(180deg, #e6eef9, #dce7f8);
      color: #1f2937;
      font-size: 15px;
    }
    * { font-family: "Sora", sans-serif; }
    header, footer { visibility: hidden; }
    .topbar { margin-bottom: 12px; }
    .main .block-container {
      max-width: none;
      width: 100%;
      padding-top: 16px;
      padding-bottom: 60px;
      padding-left: 16px;
      padding-right: 16px;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: linear-gradient(120deg, #0d4a92, #1b5faf);
      color: #ffffff;
      padding: 18px 24px;
      border-radius: 0;
      box-shadow: 0 16px 30px rgba(15, 23, 42, 0.08);
    }
    .topbar * { color: #ffffff !important; }
    .topbar .brand {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .topbar .brand img {
      width: 58px;
      height: 58px;
      border-radius: 12px;
      background: #ffffff;
      padding: 8px;
    }
    .topbar .brand h1 {
      font-size: 24px;
      margin: 0;
      letter-spacing: 0.4px;
      color: #ffffff !important;
    }
    .topbar .brand span {
      display: block;
      font-size: 14px;
      opacity: 0.95;
      color: #ffffff !important;
    }
    .topbar .top-meta {
      text-align: right;
      font-size: 13px;
      opacity: 0.95;
      color: #ffffff !important;
    }
    .topbar { width: 100%; }
    .stButton>button {
      border-radius: 12px;
      padding: 8px 14px;
      font-size: 14px;
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 11px;
      background: #eef2ff;
      color: #0d4a92;
      margin-right: 6px;
    }
    .badge.success { background: #e6f6ec; color: #1f7a3f; }
    .badge.danger { background: #fdecec; color: #b91c1c; }

    /* Inputs */
    div[data-testid="stTextInput"] input,
    div[data-testid="stDateInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stSelectbox"] div[role="combobox"] {
      border-radius: 12px !important;
      border: 1px solid #dbe3f0 !important;
      background: #ffffff !important;
      color: #0f172a !important;
      padding: 10px 14px !important;
      font-size: 15px !important;
    }

    /* Forms as cards */
    div[data-testid="stForm"] {
      background: rgba(255, 255, 255, 0.9);
      border: 1px solid #dbe3f0;
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 16px 30px rgba(15, 23, 42, 0.08);
      margin-bottom: 18px;
    }

    /* Radio nav pills */
    div[data-testid="stRadio"] [role="radiogroup"] {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 6px;
    }
    div[data-testid="stRadio"] label {
      background: #1d4c85;
      color: #eaf2ff !important;
      padding: 8px 14px;
      border-radius: 999px;
      font-size: 14px;
      letter-spacing: 0.3px;
      border: none;
      margin: 0;
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
    }
    div[data-testid="stRadio"] label span,
    div[data-testid="stRadio"] label p,
    div[data-testid="stRadio"] label div {
      color: #eaf2ff !important;
      font-weight: 600;
    }
    div[data-testid="stRadio"] label:hover {
      background: #2b64a7;
    }
    div[data-testid="stRadio"] label input {
      display: none !important;
    }
    div[data-testid="stRadio"] label:has(input:checked) {
      background: #1990ff;
      color: #ffffff !important;
      box-shadow: 0 8px 18px rgba(25, 144, 255, 0.35);
    }
    div[data-testid="stRadio"] label:has(input:checked) span,
    div[data-testid="stRadio"] label:has(input:checked) p,
    div[data-testid="stRadio"] label:has(input:checked) div {
      color: #ffffff !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
      background: #eef2f7;
      border-right: 1px solid #dbe3f0;
    }
    section[data-testid="stSidebar"] .stExpander {
      background: #ffffff;
      border-radius: 12px;
      border: 1px solid #dbe3f0;
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
    }

    label, .stMarkdown, .stText, .stCaption {
      color: #1f2937 !important;
      font-weight: 500;
    }
    h1, h2, h3, h4, h5, h6 { color: #0f172a; }

    .jr-cell {
      font-size: 14px;
      line-height: 1.3;
      color: #0f172a;
    }
    .jr-cell.jr-ok {
      color: #0f7a2a;
      font-weight: 700;
    }
    .jr-head {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: #334155;
      font-weight: 700;
    }
    .jr-nowrap { white-space: nowrap; }
    """
    if css_text:
        st.markdown(f"<style>{css_text}\n{extra}</style>", unsafe_allow_html=True)
    else:
        st.markdown(f"<style>{extra}</style>", unsafe_allow_html=True)


def _render_topbar() -> None:
    logo_uri = _data_uri(LOGO_PATH)
    hoje = svc.data_iso_para_extenso(date.today().isoformat())
    st.markdown(
        f"""
        <div class="topbar">
          <div class="brand">
            <img src="{logo_uri}" alt="JR" />
            <div>
              <h1>JR Escala</h1>
              <span>Carregamentos, equipes e relatórios</span>
            </div>
          </div>
          <div class="top-meta">
            <div>{hoje}</div>
            <div>Sistema Streamlit</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _set_flash(kind: str, message: str) -> None:
    st.session_state["flash"] = (kind, message)


def _render_flash() -> None:
    info = st.session_state.pop("flash", None)
    if not info:
        return
    kind, message = info
    if kind == "success":
        st.success(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)


def _to_date(value: str | None) -> date:
    parsed = svc.parse_date(value or "")
    return parsed or date.today()


def _optional_date_input(label: str, value_iso: str | None, key: str) -> str | None:
    col1, col2 = st.columns([3, 1])
    with col2:
        sem_data = st.checkbox("Sem data", value=value_iso is None, key=f"{key}_none")
    with col1:
        default_date = _to_date(value_iso) if value_iso else date.today()
        picked = st.date_input(label, value=default_date, key=key, disabled=sem_data)
    return None if sem_data else picked.isoformat()


def _numero_rota_ordem(item: dict) -> tuple[int, int | str]:
    rota = (item.get("rota") or "").strip()
    numero = rota.split(" - ", 1)[0].strip() if " - " in rota else rota
    if any(ch.isalpha() for ch in numero):
        return (1, numero.upper())
    digitos = "".join(ch for ch in numero if ch.isdigit())
    if digitos:
        return (0, int(digitos))
    return (1, numero.upper())


def _request_confirm(key: str, payload: object = True) -> None:
    st.session_state[key] = payload


def _confirm_prompt(key: str, message: str) -> bool:
    st.warning(message)
    col1, col2 = st.columns(2)
    if col1.button("Confirmar", key=f"{key}_confirm"):
        st.session_state.pop(key, None)
        return True
    if col2.button("Cancelar", key=f"{key}_cancel"):
        st.session_state.pop(key, None)
        st.rerun()
    return False


def _cell(container, value: object, nowrap: bool = False, extra_class: str = "") -> None:
    texto = "-" if value in (None, "") else str(value)
    classe = "jr-cell jr-nowrap" if nowrap else "jr-cell"
    if extra_class:
        classe = f"{classe} {extra_class}"
    container.markdown(
        f'<div class="{classe}">{html.escape(texto)}</div>',
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    st.session_state.setdefault("carreg_data_iso", date.today().isoformat())
    st.session_state.setdefault(
        "carreg_data_saida_iso",
        svc.calcular_data_saida_carregamento(st.session_state["carreg_data_iso"]),
    )
    st.session_state.setdefault("permitir_mot_aj", False)
    st.session_state.setdefault("carreg_edit_id", None)
    st.session_state.setdefault("carreg_last_selected_id", None)
    st.session_state.setdefault("oficina_edit_id", None)
    st.session_state.setdefault("folga_edit_id", None)
    st.session_state.setdefault("escala_edit_id", None)
    st.session_state.setdefault("rota_edit_id", None)
    st.session_state.setdefault("caminhao_edit_id", None)
    st.session_state.setdefault("ferias_edit_id", None)
    st.session_state.setdefault("colab_edit_id", None)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_carregamentos(data_iso: str) -> list[dict]:
    return svc.listar_carregamentos(data_iso)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_colaboradores_por_funcao(funcao: str, data_iso: str | None = None) -> list[dict]:
    return svc.listar_colaboradores_por_funcao(funcao, data_iso)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_caminhoes_ativos() -> list[dict]:
    return svc.listar_caminhoes_ativos()


@st.cache_data(ttl=300, show_spinner=False)
def _cache_disponibilidade(data_iso: str, ignorar_items: tuple[tuple[str, int], ...]) -> dict:
    ignorar = dict(ignorar_items) if ignorar_items else None
    return svc.verificar_disponibilidade(data_iso, ignorar)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_colaboradores(ativos_only: bool = False) -> list[dict]:
    return svc.listar_colaboradores(ativos_only=ativos_only)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_obter_colaborador_por_id(colaborador_id: int | None) -> dict | None:
    return svc.obter_colaborador_por_id(colaborador_id)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_caminhoes(ativos_only: bool = True) -> list[dict]:
    return svc.listar_caminhoes(ativos_only=ativos_only)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_folgas(data_iso: str) -> list[dict]:
    return svc.listar_folgas(data_iso)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_folgas_por_data_saida(data_iso: str) -> list[dict]:
    return svc.listar_folgas_por_data_saida(data_iso)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_ferias() -> list[dict]:
    return svc.listar_ferias()


@st.cache_data(ttl=300, show_spinner=False)
def _cache_obter_carregamento(carregamento_id: int | None) -> dict | None:
    return svc.obter_carregamento(carregamento_id) if carregamento_id else None


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_oficinas(data_iso: str) -> list[dict]:
    return svc.listar_oficinas(data_iso)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_oficinas_por_data_saida(data_iso: str) -> list[dict]:
    return svc.listar_oficinas_por_data_saida(data_iso)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_obter_oficina(oficina_id: int | None) -> dict | None:
    return svc.obter_oficina(oficina_id) if oficina_id else None


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_rotas_semanais(dia_semana: str) -> list[dict]:
    return svc.listar_rotas_semanais(dia_semana)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_listar_escala_cd(data_iso: str) -> list[dict]:
    return svc.listar_escala_cd(data_iso)


@st.cache_data(ttl=300, show_spinner=False)
def _cache_obter_escala_cd(escala_id: int | None) -> dict | None:
    return svc.obter_escala_cd(escala_id) if escala_id else None


@st.cache_data(ttl=120, show_spinner=False)
def _cache_consultar_log_carregamentos(filtros_items: tuple[tuple[str, object], ...]) -> list[dict]:
    return svc.consultar_log_carregamentos(dict(filtros_items))


def _clear_cached_data() -> None:
    st.cache_data.clear()


@st.cache_resource(show_spinner=False)
def _init_database_once() -> bool:
    init_db()
    return True


def _assistentes_sidebar(data_iso: str) -> None:
    if not st.sidebar.checkbox("Mostrar listas do dia", value=False, key="sidebar_lists_enabled"):
        return

    with st.sidebar.expander("Rotas pendentes", expanded=False):
        registros = _cache_listar_carregamentos(data_iso)
        pendentes = []
        for item in registros:
            if item.get("revisado"):
                continue
            rota = item.get("rota") or svc.DISPLAY_VAZIO
            placa = (item.get("placa") or "").strip() or svc.DISPLAY_VAZIO
            motorista = item.get("motorista_nome") or svc.DISPLAY_VAZIO
            pendentes.append(
                {
                    "rota": rota,
                    "label": f"{rota} | {placa} | {motorista}",
                }
            )
        pendentes.sort(key=_numero_rota_ordem)
        if not pendentes:
            st.write("Sem pendências.")
        else:
            for item in pendentes:
                st.write(f"- {item['label']}")

    with st.sidebar.expander("Disponíveis do dia", expanded=False):
        motoristas = _cache_listar_colaboradores_por_funcao("Motorista", data_iso)
        ajudantes = _cache_listar_colaboradores_por_funcao("Ajudante", data_iso)
        st.write("Motoristas")
        if motoristas:
            for item in sorted([m.get("nome") for m in motoristas if m.get("nome")]):
                st.write(f"- {item}")
        else:
            st.write("Nenhum motorista.")
        st.write("Ajudantes")
        if ajudantes:
            for item in sorted([a.get("nome") for a in ajudantes if a.get("nome")]):
                st.write(f"- {item}")
        else:
            st.write("Nenhum ajudante.")


def page_carregamentos() -> None:
    st.subheader("Carregamentos")

    prev_data = st.session_state.get("carreg_data_iso")
    prev_saida = st.session_state.get("carreg_data_saida_iso")

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        data_iso = st.date_input(
            "Data",
            value=_to_date(st.session_state["carreg_data_iso"]),
            key="carreg_data_input",
        ).isoformat()
    with col2:
        data_saida_iso = st.date_input(
            "Data saída",
            value=_to_date(st.session_state.get("carreg_data_saida_iso") or data_iso),
            key="carreg_saida_input",
        ).isoformat()
    with col3:
        permitir_mot_aj = st.checkbox(
            "Motorista como ajudante",
            value=st.session_state.get("permitir_mot_aj", False),
            key="permitir_mot_aj",
        )

    if prev_data and prev_data != data_iso:
        st.session_state["carreg_edit_id"] = None
    if prev_saida and prev_saida != data_saida_iso:
        st.session_state["carreg_edit_id"] = None

    st.session_state["carreg_data_iso"] = data_iso
    st.session_state["carreg_data_saida_iso"] = data_saida_iso

    registros = _cache_listar_carregamentos(data_iso)
    if not registros:
        svc.preencher_carregamentos_automaticos(data_iso, data_saida_iso)
        _clear_cached_data()
        registros = _cache_listar_carregamentos(data_iso)

    for item in registros:
        item["data_saida"] = svc.obter_data_saida_registro(item)

    total_registros = len(registros)
    pendentes = sum(1 for item in registros if not item.get("revisado"))
    preenchidas = total_registros - pendentes

    st.markdown(
        f"""
        <span class="badge">Data base {svc.data_iso_para_br(data_iso)}</span>
        <span class="badge">Total: {total_registros}</span>
        <span class="badge success">Preenchidas: {preenchidas}</span>
        <span class="badge danger">Pendentes: {pendentes}</span>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("carreg_confirm_recarregar"):
        if _confirm_prompt("carreg_confirm_recarregar", "Recarregar rotas semanais?"):
            try:
                svc.limpar_rotas_suprimidas(data_iso)
                inseridos = svc.preencher_carregamentos_automaticos(data_iso, data_saida_iso)
                if inseridos:
                    _set_flash("success", f"{inseridos} rota(s) semanal(is) adicionada(s).")
                else:
                    _set_flash("success", "Todas as rotas semanais ja estao carregadas.")
            except Exception as exc:
                _set_flash("error", f"Erro ao recarregar rotas semanais: {exc}")
            _clear_cached_data()
            st.rerun()
    elif st.session_state.get("carreg_confirm_limpar"):
        if _confirm_prompt(
            "carreg_confirm_limpar",
            "Limpar alterações do dia e recarregar rotas semanais?",
        ):
            try:
                registros_dia = _cache_listar_carregamentos(data_iso)
                for item in registros_dia:
                    svc.remover_carregamento_completo(item["id"])
                svc.limpar_rotas_suprimidas(data_iso)
                inseridos = svc.preencher_carregamentos_automaticos(data_iso, data_saida_iso)
                if registros_dia and inseridos:
                    msg = f"Alterações removidas. {inseridos} rota(s) semanal(is) recarregada(s)."
                elif registros_dia:
                    msg = "Alterações removidas. Nenhuma rota semanal para recarregar."
                elif inseridos:
                    msg = f"{inseridos} rota(s) semanal(is) carregada(s)."
                else:
                    msg = "Nada para limpar neste dia."
                _set_flash("success", msg)
            except Exception as exc:
                _set_flash("error", f"Erro ao limpar alterações: {exc}")
            _clear_cached_data()
            st.rerun()
    elif st.session_state.get("carreg_confirm_dup") is not None:
        dup_id = st.session_state.get("carreg_confirm_dup")
        if _confirm_prompt("carreg_confirm_dup", f"Duplicar carregamento #{dup_id}?"):
            try:
                svc.duplicar_carregamento(dup_id)
                _set_flash(
                    "success", "Carregamento duplicado. Placa, motorista e ajudante ficaram em branco."
                )
            except Exception as exc:
                _set_flash("error", f"Erro ao duplicar: {exc}")
            st.session_state["carreg_edit_id"] = None
            _clear_cached_data()
            st.rerun()
    elif st.session_state.get("carreg_confirm_excluir") is not None:
        excluir_id = st.session_state.get("carreg_confirm_excluir")
        if _confirm_prompt("carreg_confirm_excluir", f"Excluir carregamento #{excluir_id}?"):
            try:
                registro = _cache_obter_carregamento(excluir_id)
                if registro:
                    svc.registrar_rota_suprimida(registro.get("data"), registro.get("rota"))
                svc.remover_carregamento_completo(excluir_id)
                _set_flash("success", "Carregamento excluído.")
            except Exception as exc:
                _set_flash("error", f"Erro ao excluir: {exc}")
            st.session_state["carreg_edit_id"] = None
            _clear_cached_data()
            st.rerun()

    action_cols = st.columns([2, 2, 2])
    with action_cols[0]:
        if st.button("Recarregar rotas semanais", key="carreg_recarregar"):
            _request_confirm("carreg_confirm_recarregar")
    with action_cols[1]:
        if st.button("Limpar alterações", key="carreg_limpar"):
            _request_confirm("carreg_confirm_limpar")
    with action_cols[2]:
        if st.button("Gerar relatório", key="carreg_relatorio"):
            linhas = []
            cores_obs = []
            for item in registros:
                valores, cor = _linha_relatorio_carregamento(item)
                linhas.append(valores)
                cores_obs.append(cor)
            caminho = desenhar_relatorio_carregamentos(
                data_iso, data_saida_iso, linhas, len(registros), cores_obs
            )
            if caminho.exists():
                st.download_button(
                    "Baixar relatório",
                    data=caminho.read_bytes(),
                    file_name=caminho.name,
                    mime="image/png",
                    key="carreg_relatorio_download",
                )

    st.markdown("### Carregamentos do dia")
    form_key_bases = [
        "carreg_form_data",
        "carreg_form_saida",
        "carreg_form_placa",
        "carreg_form_rota_num",
        "carreg_form_rota_destino",
        "carreg_form_obs",
        "carreg_form_motorista",
        "carreg_form_ajudante",
        "carreg_form_obs_extra",
        "carreg_form_cor",
    ]

    def _reset_carreg_form_state() -> None:
        for key in list(st.session_state):
            if any(key == base or key.startswith(f"{base}_") for base in form_key_bases):
                st.session_state.pop(key, None)

    carregamentos_dia = sorted(registros, key=_numero_rota_ordem)
    label_map: dict[int | None, str] = {None: "Selecionar carregamento"}
    option_ids: list[int | None] = [None]
    for item in carregamentos_dia:
        cid = item.get("id")
        if cid is None:
            continue
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            continue
        rota = item.get("rota") or svc.DISPLAY_VAZIO
        placa = (item.get("placa") or "").strip() or svc.DISPLAY_VAZIO
        motorista = item.get("motorista_nome") or svc.DISPLAY_VAZIO
        status = "OK" if item.get("revisado") else "PEND"
        label_map[cid] = f"[{status}] {rota} | {placa} | {motorista}"
        option_ids.append(cid)

    edit_id = st.session_state.get("carreg_edit_id")
    try:
        edit_id = int(edit_id) if edit_id is not None else None
    except (TypeError, ValueError):
        edit_id = None
    st.session_state["carreg_edit_id"] = edit_id
    index = option_ids.index(edit_id) if edit_id in option_ids else 0

    # Limpa estado legado do selectbox (quando a key guardava texto/tupla).
    if "carreg_select" in st.session_state and not isinstance(
        st.session_state.get("carreg_select"), (int, type(None))
    ):
        st.session_state.pop("carreg_select", None)

    selected_id = st.selectbox(
        "Selecionar carregamento",
        option_ids,
        index=index,
        key="carreg_select",
        format_func=lambda cid: label_map.get(cid, "Selecionar carregamento"),
    )
    try:
        selected_id = int(selected_id) if selected_id is not None else None
    except (TypeError, ValueError):
        selected_id = None

    st.session_state["carreg_edit_id"] = selected_id
    if selected_id != st.session_state.get("carreg_last_selected_id"):
        _reset_carreg_form_state()
        st.session_state["carreg_last_selected_id"] = selected_id
    st.caption("PEND = pendente, OK = revisado")

    edit_id = st.session_state.get("carreg_edit_id")
    edit_item = _cache_obter_carregamento(edit_id) if edit_id else None
    edit_data = svc.parse_date(edit_item.get("data") or "") if edit_item else None
    base_data = svc.parse_date(data_iso)
    if edit_item and edit_data and base_data and edit_data != base_data:
        st.session_state["carreg_edit_id"] = None
        edit_item = None
    if edit_item:
        edit_item["data_saida"] = svc.obter_data_saida_registro(edit_item)

    form_key_suffix = str(edit_id) if edit_id else "novo"

    rota_num = ""
    rota_destino = ""
    if edit_item and edit_item.get("rota"):
        rota_texto = edit_item.get("rota") or ""
        if " - " in rota_texto:
            rota_num, rota_destino = rota_texto.split(" - ", 1)
            rota_num = rota_num.strip()
            rota_destino = rota_destino.strip()
        else:
            rota_num = rota_texto.strip()

    ignorar = (("carregamento_id", edit_id),) if edit_id else ()
    disponibilidade = _cache_disponibilidade(data_iso, ignorar)

    motoristas = _cache_listar_colaboradores_por_funcao("Motorista")
    ajudantes_base = _cache_listar_colaboradores_por_funcao("Ajudante")
    ajudantes_ids = {a.get("id") for a in ajudantes_base}
    ajudantes = ajudantes_base + [
        {
            "id": m["id"],
            "nome": f"{m['nome']} {svc.MOTORISTA_AJUDANTE_TAG}",
            "foto": m.get("foto"),
            "mot_aj": True,
        }
        for m in motoristas
        if m.get("id") not in ajudantes_ids
    ]
    if not permitir_mot_aj:
        ajudantes = [a for a in ajudantes if not a.get("mot_aj")]

    caminhoes = _cache_listar_caminhoes_ativos()

    def _filtrar_disponiveis(lista, indisponiveis, selecionado):
        resultado = []
        for item in lista:
            cid = item.get("id")
            if cid in indisponiveis and cid != selecionado:
                continue
            resultado.append(item)
        return resultado

    motoristas_disp = _filtrar_disponiveis(
        motoristas, disponibilidade.get("motoristas", set()), edit_item.get("motorista_id") if edit_item else None
    )
    ajudantes_disp = _filtrar_disponiveis(
        ajudantes, disponibilidade.get("ajudantes", set()), edit_item.get("ajudante_id") if edit_item else None
    )

    def _filtrar_caminhoes():
        resultado = []
        for cam in caminhoes:
            placa = (cam.get("placa") or "").upper()
            if placa in disponibilidade.get("caminhoes", set()) and placa != (edit_item.get("placa") if edit_item else None):
                continue
            resultado.append(placa)
        return resultado

    caminhoes_disp = _filtrar_caminhoes()

    with st.form("carreg_form"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            form_data_iso = st.date_input(
                "Data",
                value=_to_date(edit_item.get("data") if edit_item else data_iso),
                key=f"carreg_form_data_{form_key_suffix}",
            ).isoformat()
        with col_b:
            form_data_saida = st.date_input(
                "Data saída",
                value=_to_date(edit_item.get("data_saida") if edit_item else data_saida_iso),
                key=f"carreg_form_saida_{form_key_suffix}",
            ).isoformat()
        with col_c:
            placa_default = (edit_item.get("placa") or "") if edit_item else ""
            placa_options = [svc.VALOR_SEM_CAMINHAO] + caminhoes_disp
            placa_index = 0
            if placa_default and placa_default in placa_options:
                placa_index = placa_options.index(placa_default)
            placa_escolhida = st.selectbox(
                "Placa", placa_options, index=placa_index, key=f"carreg_form_placa_{form_key_suffix}"
            )
            placa_valor = None if placa_escolhida == svc.VALOR_SEM_CAMINHAO else placa_escolhida

        col_d, col_e, col_f = st.columns(3)
        with col_d:
            rota_num_valor = st.text_input("Rota (número)", value=rota_num, key=f"carreg_form_rota_num_{form_key_suffix}")
        with col_e:
            rota_destino_valor = st.text_input("Destino", value=rota_destino, key=f"carreg_form_rota_destino_{form_key_suffix}")
        with col_f:
            obs_opcoes = svc.OBSERVACAO_OPCOES
            obs_index = obs_opcoes.index(edit_item.get("observacao")) if edit_item and edit_item.get("observacao") in obs_opcoes else 0
            observacao_valor = st.selectbox(
                "Observação padrão", obs_opcoes, index=obs_index, key=f"carreg_form_obs_{form_key_suffix}"
            )

        col_g, col_h, col_i = st.columns(3)
        with col_g:
            motorista_options = [svc.VALOR_SEM_MOTORISTA]
            motorista_map = {svc.VALOR_SEM_MOTORISTA: None}
            for mot in motoristas_disp:
                label = f"{mot.get('nome')} (#{mot.get('id')})"
                motorista_options.append(label)
                motorista_map[label] = mot.get("id")
            motorista_sel = svc.VALOR_SEM_MOTORISTA
            if edit_item and edit_item.get("motorista_id"):
                for label, mid in motorista_map.items():
                    if mid == edit_item.get("motorista_id"):
                        motorista_sel = label
                        break
            motorista_escolhido = st.selectbox(
                "Motorista",
                motorista_options,
                index=motorista_options.index(motorista_sel),
                key=f"carreg_form_motorista_{form_key_suffix}",
            )
            motorista_id = motorista_map.get(motorista_escolhido)
        with col_h:
            ajudante_options = [svc.VALOR_SEM_AJUDANTE]
            ajudante_map = {svc.VALOR_SEM_AJUDANTE: None}
            for aju in ajudantes_disp:
                label = f"{aju.get('nome')} (#{aju.get('id')})"
                ajudante_options.append(label)
                ajudante_map[label] = aju.get("id")
            ajudante_sel = svc.VALOR_SEM_AJUDANTE
            if edit_item and edit_item.get("ajudante_id"):
                for label, aid in ajudante_map.items():
                    if aid == edit_item.get("ajudante_id"):
                        ajudante_sel = label
                        break
            ajudante_escolhido = st.selectbox(
                "Ajudante",
                ajudante_options,
                index=ajudante_options.index(ajudante_sel),
                key=f"carreg_form_ajudante_{form_key_suffix}",
            )
            ajudante_id = ajudante_map.get(ajudante_escolhido)
        with col_i:
            obs_extra = st.text_input(
                "Observação extra",
                value=(edit_item.get("observacao_extra") or "") if edit_item else "",
                key=f"carreg_form_obs_extra_{form_key_suffix}",
            )

        col_j, col_k = st.columns(2)
        with col_j:
            cor_labels = ["Sem cor"] + [label for label, cor in svc.OBS_MARCADORES if cor]
            cor_map = {"Sem cor": None}
            for label, cor in svc.OBS_MARCADORES:
                if cor:
                    cor_map[label] = cor
            cor_default = "Sem cor"
            if edit_item and edit_item.get("observacao_cor"):
                for label, cor in cor_map.items():
                    if cor == edit_item.get("observacao_cor"):
                        cor_default = label
                        break
            cor_escolhida = st.selectbox(
                "Cor da observação",
                cor_labels,
                index=cor_labels.index(cor_default),
                key=f"carreg_form_cor_{form_key_suffix}",
            )
            observacao_cor = cor_map.get(cor_escolhida)
        with col_k:
            st.write("")

        submit = st.form_submit_button("Atualizar" if edit_item else "Salvar")

    if submit:
        if not rota_num_valor or not rota_destino_valor:
            _set_flash("error", "Informe rota e destino.")
            st.rerun()
        rota_texto = f"{rota_num_valor.strip()} - {rota_destino_valor.strip()}"
        ignorar = (("carregamento_id", edit_id),) if edit_id else ()
        disponibilidade_submit = _cache_disponibilidade(form_data_iso, ignorar)
        indis = disponibilidade_submit.get("motoristas", set()).union(
            disponibilidade_submit.get("ajudantes", set())
        )
        if motorista_id and motorista_id in indis:
            _set_flash("error", "Motorista indisponível nesta data.")
            st.rerun()
        if ajudante_id and ajudante_id in indis:
            _set_flash("error", "Ajudante indisponível nesta data.")
            st.rerun()
        if placa_valor and placa_valor.upper() in disponibilidade_submit.get("caminhoes", set()):
            _set_flash("error", "Caminhão indisponível nesta data.")
            st.rerun()
        try:
            if edit_item:
                registro_anterior = _cache_obter_carregamento(edit_item["id"])
                svc.atualizar_carregamento(
                    edit_item["id"],
                    form_data_iso,
                    form_data_saida,
                    rota_texto,
                    placa_valor,
                    motorista_id,
                    ajudante_id,
                    observacao_valor,
                    obs_extra,
                    observacao_cor,
                )
                if registro_anterior and registro_anterior.get("rota") != rota_texto:
                    svc.registrar_rota_suprimida(registro_anterior.get("data"), registro_anterior.get("rota"))
                svc.remover_bloqueios_por_carregamento(edit_item["id"])
                svc.criar_bloqueios_para_carregamento(
                    edit_item["id"], form_data_iso, [motorista_id, ajudante_id], observacao_valor
                )
                _set_flash("success", "Carregamento atualizado.")
            else:
                novo_id = svc.salvar_carregamento(
                    form_data_iso,
                    rota_texto,
                    placa_valor,
                    motorista_id,
                    ajudante_id,
                    observacao_valor,
                    obs_extra,
                    observacao_cor,
                    form_data_saida,
                    revisado=True,
                )
                svc.criar_bloqueios_para_carregamento(
                    novo_id, form_data_iso, [motorista_id, ajudante_id], observacao_valor
                )
                _set_flash("success", "Carregamento salvo.")
        except Exception as exc:
            _set_flash("error", f"Erro ao salvar: {exc}")
        _clear_cached_data()
        st.session_state["carreg_edit_id"] = None
        st.session_state["carreg_select"] = None
        st.session_state["carreg_last_selected_id"] = None
        _reset_carreg_form_state()
        st.rerun()

    if edit_item:
        if st.button("Cancelar edição", key="carreg_cancelar"):
            st.session_state["carreg_edit_id"] = None
            st.session_state["carreg_select"] = None
            st.session_state["carreg_last_selected_id"] = None
            _reset_carreg_form_state()
            st.rerun()

    st.markdown("### Lista do dia")
    if registros:
        col_sizes = [3, 1.2, 2.4, 2.4, 2.8, 1.6, 3]
        header = st.columns(col_sizes)
        header[0].markdown('<div class="jr-head">Rota</div>', unsafe_allow_html=True)
        header[1].markdown('<div class="jr-head">Placa</div>', unsafe_allow_html=True)
        header[2].markdown('<div class="jr-head">Motorista</div>', unsafe_allow_html=True)
        header[3].markdown('<div class="jr-head">Ajudante</div>', unsafe_allow_html=True)
        header[4].markdown('<div class="jr-head">Observação</div>', unsafe_allow_html=True)
        header[5].markdown('<div class="jr-head">Saída</div>', unsafe_allow_html=True)
        header[6].markdown('<div class="jr-head">Ações</div>', unsafe_allow_html=True)
        for item in registros:
            obs = item.get("observacao") or ""
            obs_extra = item.get("observacao_extra") or ""
            if obs == "0":
                obs_texto = "Sem observação"
            elif obs and obs_extra:
                obs_texto = f"{obs} - {obs_extra}"
            elif obs:
                obs_texto = obs
            elif obs_extra:
                obs_texto = obs_extra
            else:
                obs_texto = "-"
            saida_valor = (
                svc.data_iso_para_br(item.get("data_saida"))
                if item.get("data_saida")
                else "-"
            )
            row_class = "jr-ok" if item.get("revisado") else ""
            cols = st.columns(col_sizes)
            _cell(cols[0], item.get("rota") or "-", extra_class=row_class)
            _cell(cols[1], item.get("placa") or "-", nowrap=True, extra_class=row_class)
            _cell(cols[2], item.get("motorista_nome") or "-", extra_class=row_class)
            _cell(cols[3], item.get("ajudante_nome") or "-", extra_class=row_class)
            _cell(cols[4], obs_texto, extra_class=row_class)
            _cell(cols[5], saida_valor, nowrap=True, extra_class=row_class)
            action_cols = cols[6].columns([1, 1, 1])
            item_id = item.get("id")
            if action_cols[0].button(
                "Editar", key=f"carreg_row_edit_{item_id}", use_container_width=True
            ):
                st.session_state["carreg_edit_id"] = item_id
                st.session_state["carreg_select"] = item_id
                st.session_state["carreg_last_selected_id"] = item_id
                _reset_carreg_form_state()
                st.rerun()
            if action_cols[1].button(
                "Duplicar", key=f"carreg_row_dup_{item_id}", use_container_width=True
            ):
                _request_confirm("carreg_confirm_dup", item_id)
            if action_cols[2].button(
                "Excluir", key=f"carreg_row_del_{item_id}", use_container_width=True
            ):
                _request_confirm("carreg_confirm_excluir", item_id)
    else:
        st.info("Nenhum carregamento cadastrado.")



def page_oficinas() -> None:
    st.subheader("Oficinas")
    prev_data = st.session_state.get("oficina_data_iso")
    col1, col2 = st.columns(2)
    with col1:
        data_iso = st.date_input("Data", value=_to_date(date.today().isoformat()), key="oficina_data").isoformat()
    with col2:
        data_saida_iso = st.date_input(
            "Data saída",
            value=_to_date(svc.calcular_data_saida_padrao(data_iso) or data_iso),
            key="oficina_saida",
        ).isoformat()

    if prev_data and prev_data != data_iso:
        st.session_state["oficina_edit_id"] = None
    st.session_state["oficina_data_iso"] = data_iso

    registros = _cache_listar_oficinas(data_iso)
    oficina_edit_id = st.session_state.get("oficina_edit_id")
    disponibilidade = _cache_disponibilidade(
        data_iso,
        (("oficina_id", oficina_edit_id),) if oficina_edit_id else (),
    )
    motoristas = _cache_listar_colaboradores_por_funcao("Motorista")
    caminhoes = _cache_listar_caminhoes_ativos()

    if st.button("Gerar relatório", key="oficina_relatorio"):
        data_ref = data_saida_iso or data_iso
        reg_saida = _cache_listar_oficinas_por_data_saida(data_ref)
        caminho = gerar_relatorio_oficinas(data_iso, data_saida_iso, reg_saida)
        if caminho.exists():
            st.download_button(
                "Baixar relatório",
                data=caminho.read_bytes(),
                file_name=caminho.name,
                mime="image/png",
                key="oficina_relatorio_download",
            )

    if st.session_state.get("oficina_confirm_excluir") is not None:
        excluir_id = st.session_state.get("oficina_confirm_excluir")
        if _confirm_prompt("oficina_confirm_excluir", f"Excluir oficina #{excluir_id}?"):
            try:
                svc.excluir_oficina(excluir_id)
                _set_flash("success", "Oficina excluída.")
            except Exception as exc:
                _set_flash("error", f"Erro ao excluir: {exc}")
            st.session_state["oficina_edit_id"] = None
            _clear_cached_data()
            st.rerun()

    edit_id = st.session_state.get("oficina_edit_id")
    edit_item = _cache_obter_oficina(edit_id) if edit_id else None
    if edit_item and edit_item.get("data") != data_iso:
        st.session_state["oficina_edit_id"] = None
        edit_item = None

    def _filtrar_motoristas():
        resultado = []
        indis = disponibilidade.get("motoristas", set())
        for mot in motoristas:
            if mot.get("id") in indis and mot.get("id") != (edit_item.get("motorista_id") if edit_item else None):
                continue
            resultado.append(mot)
        return resultado

    def _filtrar_caminhoes():
        resultado = []
        indis = disponibilidade.get("caminhoes", set())
        for cam in caminhoes:
            placa = (cam.get("placa") or "").upper()
            if placa in indis and placa != (edit_item.get("placa") if edit_item else None):
                continue
            resultado.append(placa)
        return resultado

    motoristas_disp = _filtrar_motoristas()
    caminhoes_disp = _filtrar_caminhoes()

    with st.form("oficina_form"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            form_data = st.date_input(
                "Data",
                value=_to_date(edit_item.get("data") if edit_item else data_iso),
                key="oficina_form_data",
            ).isoformat()
        with col_b:
            form_saida = st.date_input(
                "Data saída",
                value=_to_date(edit_item.get("data_saida") if edit_item else data_saida_iso),
                key="oficina_form_saida",
            ).isoformat()
        with col_c:
            placa_default = (edit_item.get("placa") or "") if edit_item else ""
            placa_opts = caminhoes_disp if caminhoes_disp else [""]
            placa_index = placa_opts.index(placa_default) if placa_default in placa_opts else 0
            placa = st.selectbox(
                "Placa",
                placa_opts,
                index=placa_index,
                key="oficina_form_placa",
                format_func=lambda v: v or "Sem caminhão",
            )

        col_d, col_e, col_f = st.columns(3)
        with col_d:
            mot_opts = [svc.VALOR_SEM_MOTORISTA]
            mot_map = {svc.VALOR_SEM_MOTORISTA: None}
            for mot in motoristas_disp:
                label = f"{mot.get('nome')} (#{mot.get('id')})"
                mot_opts.append(label)
                mot_map[label] = mot.get("id")
            mot_sel = svc.VALOR_SEM_MOTORISTA
            if edit_item and edit_item.get("motorista_id"):
                for label, mid in mot_map.items():
                    if mid == edit_item.get("motorista_id"):
                        mot_sel = label
                        break
            mot_escolhido = st.selectbox(
                "Motorista", mot_opts, index=mot_opts.index(mot_sel), key="oficina_form_motorista"
            )
            motorista_id = mot_map.get(mot_escolhido)
        with col_e:
            observacao = st.text_input(
                "Observação",
                value=(edit_item.get("observacao") or "") if edit_item else "",
                key="oficina_form_obs",
            )
        with col_f:
            observacao_extra = st.text_input(
                "Observação extra",
                value=(edit_item.get("observacao_extra") or "") if edit_item else "",
                key="oficina_form_obs_extra",
            )

        cor_labels = ["Sem cor"] + [label for label, cor in svc.OBS_MARCADORES if cor]
        cor_map = {"Sem cor": None}
        for label, cor in svc.OBS_MARCADORES:
            if cor:
                cor_map[label] = cor
        cor_default = "Sem cor"
        if edit_item and edit_item.get("observacao_cor"):
            for label, cor in cor_map.items():
                if cor == edit_item.get("observacao_cor"):
                    cor_default = label
                    break
        observacao_cor = st.selectbox(
            "Cor da observação",
            cor_labels,
            index=cor_labels.index(cor_default),
            key="oficina_form_cor",
        )

        submit = st.form_submit_button("Atualizar" if edit_item else "Salvar")

    if submit:
        if not placa:
            _set_flash("error", "Informe a placa.")
            st.rerun()
        try:
            if edit_item:
                svc.editar_oficina(
                    edit_item["id"],
                    motorista_id,
                    placa,
                    observacao,
                    observacao_extra,
                    form_saida,
                    cor_map.get(observacao_cor),
                )
                _set_flash("success", "Oficina atualizada.")
            else:
                svc.salvar_oficina(
                    form_data,
                    motorista_id,
                    placa,
                    observacao,
                    observacao_extra,
                    form_saida,
                    cor_map.get(observacao_cor),
                )
                _set_flash("success", "Oficina salva.")
        except Exception as exc:
            _set_flash("error", f"Erro ao salvar: {exc}")
        st.session_state["oficina_edit_id"] = None
        _clear_cached_data()
        st.rerun()

    if edit_item:
        if st.button("Cancelar edição", key="oficina_cancelar"):
            st.session_state["oficina_edit_id"] = None
            st.rerun()

    if registros:
        col_sizes = [1.2, 2.2, 2.8, 1.4, 2.4]
        header = st.columns(col_sizes)
        header[0].markdown('<div class="jr-head">Placa</div>', unsafe_allow_html=True)
        header[1].markdown('<div class="jr-head">Motorista</div>', unsafe_allow_html=True)
        header[2].markdown('<div class="jr-head">Observação</div>', unsafe_allow_html=True)
        header[3].markdown('<div class="jr-head">Saída</div>', unsafe_allow_html=True)
        header[4].markdown('<div class="jr-head">Ações</div>', unsafe_allow_html=True)
        for item in registros:
            cols = st.columns(col_sizes)
            _cell(cols[0], item.get("placa") or "-", nowrap=True)
            _cell(cols[1], item.get("motorista_nome") or "-")
            _cell(cols[2], item.get("observacao") or "-")
            _cell(cols[3], item.get("data_saida") or "-", nowrap=True)
            action_cols = cols[4].columns(2)
            item_id = item.get("id")
            if action_cols[0].button(
                "Editar", key=f"oficina_row_edit_{item_id}", use_container_width=True
            ):
                st.session_state["oficina_edit_id"] = item_id
            if action_cols[1].button(
                "Excluir", key=f"oficina_row_del_{item_id}", use_container_width=True
            ):
                _request_confirm("oficina_confirm_excluir", item_id)
    else:
        st.info("Nenhuma oficina cadastrada.")


def page_folgas() -> None:
    st.subheader("Folgas")
    prev_data = st.session_state.get("folga_data_iso")
    data_iso = st.date_input("Data", value=_to_date(date.today().isoformat()), key="folga_data").isoformat()
    data_saida_iso = svc.calcular_data_saida_padrao(data_iso)
    st.caption(f"Data base {svc.data_iso_para_br(data_iso)}")

    if prev_data and prev_data != data_iso:
        st.session_state["folga_edit_id"] = None
    st.session_state["folga_data_iso"] = data_iso

    registros = _cache_listar_folgas(data_iso)
    colaboradores = _cache_listar_colaboradores(ativos_only=True)
    edit_id = st.session_state.get("folga_edit_id")
    disponibilidade = _cache_disponibilidade(data_iso, (("folga_id", edit_id),) if edit_id else ())

    if st.button("Gerar relatório", key="folga_relatorio"):
        data_ref = data_saida_iso or data_iso
        reg_saida = _cache_listar_folgas_por_data_saida(data_ref)
        caminho = gerar_relatorio_folgas(data_iso, data_saida_iso, reg_saida)
        if caminho.exists():
            st.download_button(
                "Baixar relatório",
                data=caminho.read_bytes(),
                file_name=caminho.name,
                mime="image/png",
                key="folga_relatorio_download",
            )

    if st.session_state.get("folga_confirm_excluir") is not None:
        excluir_id = st.session_state.get("folga_confirm_excluir")
        if _confirm_prompt("folga_confirm_excluir", f"Excluir folga #{excluir_id}?"):
            try:
                svc.remover_folga(excluir_id)
                _set_flash("success", "Folga excluída.")
            except Exception as exc:
                _set_flash("error", f"Erro ao excluir: {exc}")
            st.session_state["folga_edit_id"] = None
            _clear_cached_data()
            st.rerun()

    edit_id = st.session_state.get("folga_edit_id")
    edit_item = None
    if edit_id:
        for item in registros:
            if item.get("folga_id") == edit_id:
                edit_item = item
                break

    colab_opts = ["Selecionar colaborador"]
    colab_map = {"Selecionar colaborador": None}
    indis = disponibilidade.get("motoristas", set()).union(disponibilidade.get("ajudantes", set()))
    for col in colaboradores:
        if col.get("id") in indis and col.get("id") != (edit_item.get("colaborador_id") if edit_item else None):
            continue
        label = f"{col.get('nome')} ({col.get('funcao')}) (#{col.get('id')})"
        colab_opts.append(label)
        colab_map[label] = col.get("id")

    with st.form("folga_form"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            form_data = st.date_input(
                "Data",
                value=_to_date(edit_item.get("data") if edit_item else data_iso),
                key="folga_form_data",
            ).isoformat()
        with col_b:
            form_data_fim = _optional_date_input(
                "Data fim (opcional)",
                edit_item.get("data_fim") if edit_item else None,
                "folga_form_data_fim",
            )
        with col_c:
            colab_sel = "Selecionar colaborador"
            if edit_item and edit_item.get("colaborador_id"):
                for label, cid in colab_map.items():
                    if cid == edit_item.get("colaborador_id"):
                        colab_sel = label
                        break
            colab_label = st.selectbox(
                "Colaborador",
                colab_opts,
                index=colab_opts.index(colab_sel),
                key="folga_form_colab",
            )
            colaborador_id = colab_map.get(colab_label)

        submit = st.form_submit_button("Atualizar" if edit_item else "Salvar")

    if submit:
        if not colaborador_id:
            _set_flash("error", "Selecione um colaborador.")
            st.rerun()
        try:
            if edit_item:
                svc.editar_folga(
                    edit_id,
                    form_data,
                    form_data_fim,
                    data_saida_iso,
                    colaborador_id,
                    None,
                    None,
                    None,
                )
                _set_flash("success", "Folga atualizada.")
            else:
                svc.salvar_folga(
                    form_data,
                    colaborador_id,
                    form_data_fim,
                    data_saida_iso,
                    None,
                    None,
                    None,
                )
                _set_flash("success", "Folga salva.")
        except Exception as exc:
            _set_flash("error", f"Erro ao salvar: {exc}")
        st.session_state["folga_edit_id"] = None
        _clear_cached_data()
        st.rerun()

    if edit_item:
        if st.button("Cancelar edição", key="folga_cancelar"):
            st.session_state["folga_edit_id"] = None
            st.rerun()

    if registros:
        col_sizes = [2.4, 1.2, 2.2, 2.2]
        header = st.columns(col_sizes)
        header[0].markdown('<div class="jr-head">Colaborador</div>', unsafe_allow_html=True)
        header[1].markdown('<div class="jr-head">Função</div>', unsafe_allow_html=True)
        header[2].markdown('<div class="jr-head">Período</div>', unsafe_allow_html=True)
        header[3].markdown('<div class="jr-head">Ações</div>', unsafe_allow_html=True)
        for item in registros:
            fim = item.get("data_fim") or data_saida_iso
            if fim and fim != item.get("data"):
                periodo = f"{item.get('data')} -> {fim}"
            else:
                periodo = item.get("data")
            cols = st.columns(col_sizes)
            _cell(cols[0], item.get("nome") or "-")
            _cell(cols[1], item.get("funcao") or "-")
            _cell(cols[2], periodo or "-", nowrap=True)
            action_cols = cols[3].columns(2)
            item_id = item.get("folga_id")
            if action_cols[0].button(
                "Editar", key=f"folga_row_edit_{item_id}", use_container_width=True
            ):
                st.session_state["folga_edit_id"] = item_id
            if action_cols[1].button(
                "Excluir", key=f"folga_row_del_{item_id}", use_container_width=True
            ):
                _request_confirm("folga_confirm_excluir", item_id)
    else:
        st.info("Nenhuma folga cadastrada.")


def page_escala_cd() -> None:
    st.subheader("Escala (CD)")
    prev_data = st.session_state.get("escala_data_iso")
    col1, col2 = st.columns(2)
    with col1:
        data_iso = st.date_input("Data", value=_to_date(date.today().isoformat()), key="escala_data").isoformat()
    with col2:
        data_saida_iso = st.date_input(
            "Data saída",
            value=_to_date(svc.calcular_data_saida_padrao(data_iso) or data_iso),
            key="escala_saida",
        ).isoformat()

    if prev_data and prev_data != data_iso:
        st.session_state["escala_edit_id"] = None
    st.session_state["escala_data_iso"] = data_iso

    registros = _cache_listar_escala_cd(data_iso)
    edit_id = st.session_state.get("escala_edit_id")
    edit_item = _cache_obter_escala_cd(edit_id) if edit_id else None
    disponibilidade = _cache_disponibilidade(data_iso, (("escala_cd_id", edit_id),) if edit_id else ())
    motoristas = _cache_listar_colaboradores_por_funcao("Motorista")
    ajudantes = _cache_listar_colaboradores_por_funcao("Ajudante")
    ajudantes_ids = {a.get("id") for a in ajudantes}
    ajudantes = ajudantes + [
        {
            "id": m["id"],
            "nome": f"{m['nome']} {svc.MOTORISTA_AJUDANTE_TAG}",
            "foto": m.get("foto"),
            "mot_aj": True,
        }
        for m in motoristas
        if m.get("id") not in ajudantes_ids
    ]

    if st.button("Gerar relatório", key="escala_relatorio"):
        caminho = gerar_relatorio_escala_cd(data_iso, data_saida_iso, registros)
        if caminho.exists():
            st.download_button(
                "Baixar relatório",
                data=caminho.read_bytes(),
                file_name=caminho.name,
                mime="image/png",
                key="escala_relatorio_download",
            )

    if st.session_state.get("escala_confirm_excluir") is not None:
        excluir_id = st.session_state.get("escala_confirm_excluir")
        if _confirm_prompt("escala_confirm_excluir", f"Excluir escala #{excluir_id}?"):
            try:
                svc.excluir_escala_cd(excluir_id)
                _set_flash("success", "Escala (CD) excluída.")
            except Exception as exc:
                _set_flash("error", f"Erro ao excluir: {exc}")
            st.session_state["escala_edit_id"] = None
            _clear_cached_data()
            st.rerun()

    edit_id = st.session_state.get("escala_edit_id")
    edit_item = _cache_obter_escala_cd(edit_id) if edit_id else None
    if edit_item and edit_item.get("data") != data_iso:
        st.session_state["escala_edit_id"] = None
        edit_item = None

    def _filtrar(lista, indis, selecionado):
        resultado = []
        for item in lista:
            cid = item.get("id")
            if cid in indis and cid != selecionado:
                continue
            resultado.append(item)
        return resultado

    mot_disp = _filtrar(motoristas, disponibilidade.get("motoristas", set()), edit_item.get("motorista_id") if edit_item else None)
    aju_disp = _filtrar(ajudantes, disponibilidade.get("ajudantes", set()), edit_item.get("ajudante_id") if edit_item else None)

    with st.form("escala_form"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            form_data = st.date_input(
                "Data",
                value=_to_date(edit_item.get("data") if edit_item else data_iso),
                key="escala_form_data",
            ).isoformat()
        with col_b:
            mot_opts = [svc.VALOR_SEM_MOTORISTA]
            mot_map = {svc.VALOR_SEM_MOTORISTA: None}
            for mot in mot_disp:
                label = f"{mot.get('nome')} (#{mot.get('id')})"
                mot_opts.append(label)
                mot_map[label] = mot.get("id")
            mot_sel = svc.VALOR_SEM_MOTORISTA
            if edit_item and edit_item.get("motorista_id"):
                for label, mid in mot_map.items():
                    if mid == edit_item.get("motorista_id"):
                        mot_sel = label
                        break
            mot_label = st.selectbox(
                "Motorista",
                mot_opts,
                index=mot_opts.index(mot_sel),
                key="escala_form_motorista",
            )
            motorista_id = mot_map.get(mot_label)
        with col_c:
            aju_opts = [svc.VALOR_SEM_AJUDANTE]
            aju_map = {svc.VALOR_SEM_AJUDANTE: None}
            for aju in aju_disp:
                label = f"{aju.get('nome')} (#{aju.get('id')})"
                aju_opts.append(label)
                aju_map[label] = aju.get("id")
            aju_sel = svc.VALOR_SEM_AJUDANTE
            if edit_item and edit_item.get("ajudante_id"):
                for label, aid in aju_map.items():
                    if aid == edit_item.get("ajudante_id"):
                        aju_sel = label
                        break
            aju_label = st.selectbox(
                "Ajudante",
                aju_opts,
                index=aju_opts.index(aju_sel),
                key="escala_form_ajudante",
            )
            ajudante_id = aju_map.get(aju_label)

        observacao = st.text_input(
            "Observação",
            value=(edit_item.get("observacao") or "") if edit_item else "",
            key="escala_form_obs",
        )

        submit = st.form_submit_button("Atualizar" if edit_item else "Salvar")

    if submit:
        disponibilidade_submit = _cache_disponibilidade(
            form_data, (("escala_cd_id", edit_id),) if edit_id else ()
        )
        indis = disponibilidade_submit.get("motoristas", set()).union(
            disponibilidade_submit.get("ajudantes", set())
        )
        if motorista_id and motorista_id in indis:
            _set_flash("error", "Motorista indisponível nesta data.")
            st.rerun()
        if ajudante_id and ajudante_id in indis:
            _set_flash("error", "Ajudante indisponível nesta data.")
            st.rerun()
        try:
            if edit_item:
                svc.editar_escala_cd(edit_id, motorista_id, ajudante_id, observacao)
                _set_flash("success", "Escala (CD) atualizada.")
            else:
                svc.adicionar_escala_cd(form_data, motorista_id, ajudante_id, observacao)
                _set_flash("success", "Escala (CD) salva.")
        except Exception as exc:
            _set_flash("error", f"Erro ao salvar: {exc}")
        st.session_state["escala_edit_id"] = None
        _clear_cached_data()
        st.rerun()

    if edit_item:
        if st.button("Cancelar edição", key="escala_cancelar"):
            st.session_state["escala_edit_id"] = None
            st.rerun()

    if registros:
        col_sizes = [2.2, 2.2, 2.8, 2]
        header = st.columns(col_sizes)
        header[0].markdown('<div class="jr-head">Motorista</div>', unsafe_allow_html=True)
        header[1].markdown('<div class="jr-head">Ajudante</div>', unsafe_allow_html=True)
        header[2].markdown('<div class="jr-head">Observação</div>', unsafe_allow_html=True)
        header[3].markdown('<div class="jr-head">Ações</div>', unsafe_allow_html=True)
        for item in registros:
            cols = st.columns(col_sizes)
            _cell(cols[0], item.get("motorista_nome") or "-")
            _cell(cols[1], item.get("ajudante_nome") or "-")
            _cell(cols[2], item.get("observacao") or "-")
            action_cols = cols[3].columns(2)
            item_id = item.get("id")
            if action_cols[0].button(
                "Editar", key=f"escala_row_edit_{item_id}", use_container_width=True
            ):
                st.session_state["escala_edit_id"] = item_id
            if action_cols[1].button(
                "Excluir", key=f"escala_row_del_{item_id}", use_container_width=True
            ):
                _request_confirm("escala_confirm_excluir", item_id)
    else:
        st.info("Nenhuma escala cadastrada.")


def page_rotas_semanais() -> None:
    st.subheader("Rotas Semanais")
    dias = svc.DIAS_SEMANA
    dia_default = dias[0][0]
    dia_labels = [label for _, label in dias]
    dia_map = {label: chave for chave, label in dias}
    dia_inv = {chave: label for chave, label in dias}

    prev_dia = st.session_state.get("rotas_dia_value")
    dia_label = st.selectbox("Dia da semana", dia_labels, key="rotas_dia")
    dia = dia_map.get(dia_label, dia_default)
    if prev_dia and prev_dia != dia:
        st.session_state["rota_edit_id"] = None
    st.session_state["rotas_dia_value"] = dia
    registros = _cache_listar_rotas_semanais(dia)

    edit_id = st.session_state.get("rota_edit_id")
    edit_item = None
    if edit_id:
        for item in registros:
            if item.get("id") == edit_id:
                edit_item = item
                break

    with st.form("rotas_form"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            dia_form_label = dia_inv.get(edit_item.get("dia_semana") if edit_item else dia, dia_label)
            dia_form_label = st.selectbox(
                "Dia da semana",
                dia_labels,
                index=dia_labels.index(dia_form_label),
                key="rotas_form_dia",
            )
            dia_form = dia_map.get(dia_form_label, dia_default)
        with col_b:
            rota_texto = st.text_input(
                "Rota",
                value=(edit_item.get("rota") or "") if edit_item else "",
                key="rotas_form_rota",
            )
        with col_c:
            destino = st.text_input(
                "Destino",
                value=(edit_item.get("destino") or "") if edit_item else "",
                key="rotas_form_destino",
            )
        observacao = st.text_input(
            "Observação",
            value=(edit_item.get("observacao") or "") if edit_item else "",
            key="rotas_form_obs",
        )
        submit = st.form_submit_button("Atualizar" if edit_item else "Salvar")

    if submit:
        if not rota_texto:
            _set_flash("error", "Informe a rota.")
            st.rerun()
        try:
            if edit_item:
                svc.editar_rota_semana(edit_id, dia_form, rota_texto, destino, observacao)
                _set_flash("success", "Rota semanal atualizada.")
            else:
                svc.adicionar_rota_semana(dia_form, rota_texto, destino, observacao)
                svc.sincronizar_rota_semana_com_carregamentos(
                    st.session_state.get("carreg_data_iso"),
                    dia_form,
                    rota_texto,
                    destino,
                    observacao,
                    st.session_state.get("carreg_data_saida_iso"),
                )
                _set_flash("success", "Rota semanal salva.")
        except Exception as exc:
            _set_flash("error", f"Erro ao salvar: {exc}")
        st.session_state["rota_edit_id"] = None
        _clear_cached_data()
        st.rerun()

    if st.session_state.get("rota_confirm_excluir") is not None:
        excluir_id = st.session_state.get("rota_confirm_excluir")
        if _confirm_prompt("rota_confirm_excluir", f"Excluir rota #{excluir_id}?"):
            try:
                svc.remover_rota_semana(excluir_id)
                _set_flash("success", "Rota semanal excluída.")
            except Exception as exc:
                _set_flash("error", f"Erro ao excluir: {exc}")
            st.session_state["rota_edit_id"] = None
            _clear_cached_data()
            st.rerun()

    if edit_item:
        if st.button("Cancelar edição", key="rotas_cancelar"):
            st.session_state["rota_edit_id"] = None
            st.rerun()

    if registros:
        col_sizes = [1.2, 2.2, 2.6, 2]
        header = st.columns(col_sizes)
        header[0].markdown('<div class="jr-head">Rota</div>', unsafe_allow_html=True)
        header[1].markdown('<div class="jr-head">Destino</div>', unsafe_allow_html=True)
        header[2].markdown('<div class="jr-head">Observação</div>', unsafe_allow_html=True)
        header[3].markdown('<div class="jr-head">Ações</div>', unsafe_allow_html=True)
        for item in registros:
            cols = st.columns(col_sizes)
            _cell(cols[0], item.get("rota") or "-")
            _cell(cols[1], item.get("destino") or "-")
            _cell(cols[2], item.get("observacao") or "-")
            action_cols = cols[3].columns(2)
            item_id = item.get("id")
            if action_cols[0].button(
                "Editar", key=f"rotas_row_edit_{item_id}", use_container_width=True
            ):
                st.session_state["rota_edit_id"] = item_id
            if action_cols[1].button(
                "Excluir", key=f"rotas_row_del_{item_id}", use_container_width=True
            ):
                _request_confirm("rota_confirm_excluir", item_id)
    else:
        st.info("Nenhuma rota cadastrada.")


def page_caminhoes() -> None:
    st.subheader("Caminhões")
    registros = _cache_listar_caminhoes(ativos_only=False)

    edit_id = st.session_state.get("caminhao_edit_id")
    edit_item = None
    if edit_id:
        for item in registros:
            if item.get("id") == edit_id:
                edit_item = item
                break

    with st.form("caminhao_form"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            placa = st.text_input(
                "Placa",
                value=(edit_item.get("placa") or "") if edit_item else "",
                key="caminhao_form_placa",
            )
        with col_b:
            modelo = st.text_input(
                "Modelo",
                value=(edit_item.get("modelo") or "") if edit_item else "",
                key="caminhao_form_modelo",
            )
        with col_c:
            observacao = st.text_input(
                "Observação",
                value=(edit_item.get("observacao") or "") if edit_item else "",
                key="caminhao_form_obs",
            )
        ativo = st.checkbox(
            "Ativo",
            value=bool(edit_item.get("ativo")) if edit_item else True,
            key="caminhao_form_ativo",
        )
        submit = st.form_submit_button("Atualizar" if edit_item else "Salvar")

    if submit:
        if not placa:
            _set_flash("error", "Informe a placa.")
            st.rerun()
        try:
            if edit_item:
                svc.editar_caminhao(edit_id, placa, modelo, observacao, ativo)
                _set_flash("success", "Caminhão atualizado.")
            else:
                svc.add_caminhao(placa, modelo, observacao)
                _set_flash("success", "Caminhão salvo.")
        except Exception as exc:
            _set_flash("error", f"Erro ao salvar: {exc}")
        st.session_state["caminhao_edit_id"] = None
        _clear_cached_data()
        st.rerun()

    if st.session_state.get("caminhao_confirm_excluir") is not None:
        excluir_id = st.session_state.get("caminhao_confirm_excluir")
        if _confirm_prompt("caminhao_confirm_excluir", f"Excluir caminhão #{excluir_id}?"):
            try:
                svc.remover_caminhao(excluir_id)
                _set_flash("success", "Caminhão excluído.")
            except Exception as exc:
                _set_flash("error", f"Erro ao excluir: {exc}")
            st.session_state["caminhao_edit_id"] = None
            _clear_cached_data()
            st.rerun()

    if edit_item:
        if st.button("Cancelar edição", key="caminhao_cancelar"):
            st.session_state["caminhao_edit_id"] = None
            st.rerun()

    if registros:
        col_sizes = [1.2, 2.0, 2.4, 1.2, 2.2]
        header = st.columns(col_sizes)
        header[0].markdown('<div class="jr-head">Placa</div>', unsafe_allow_html=True)
        header[1].markdown('<div class="jr-head">Modelo</div>', unsafe_allow_html=True)
        header[2].markdown('<div class="jr-head">Observação</div>', unsafe_allow_html=True)
        header[3].markdown('<div class="jr-head">Status</div>', unsafe_allow_html=True)
        header[4].markdown('<div class="jr-head">Ações</div>', unsafe_allow_html=True)
        for item in registros:
            cols = st.columns(col_sizes)
            _cell(cols[0], item.get("placa") or "-", nowrap=True)
            _cell(cols[1], item.get("modelo") or "-")
            _cell(cols[2], item.get("observacao") or "-")
            _cell(cols[3], "Ativo" if item.get("ativo") else "Inativo", nowrap=True)
            action_cols = cols[4].columns(2)
            item_id = item.get("id")
            if action_cols[0].button(
                "Editar", key=f"caminhao_row_edit_{item_id}", use_container_width=True
            ):
                st.session_state["caminhao_edit_id"] = item_id
            if action_cols[1].button(
                "Excluir", key=f"caminhao_row_del_{item_id}", use_container_width=True
            ):
                _request_confirm("caminhao_confirm_excluir", item_id)
    else:
        st.info("Nenhum caminhão cadastrado.")


def page_ferias() -> None:
    st.subheader("Férias")
    registros = _cache_listar_ferias()
    colaboradores = _cache_listar_colaboradores(ativos_only=True)

    edit_id = st.session_state.get("ferias_edit_id")
    edit_item = None
    if edit_id:
        for item in registros:
            if item.get("id") == edit_id:
                edit_item = item
                break

    data_inicio_ref = edit_item.get("data_inicio") if edit_item else None
    session_inicio = st.session_state.get("ferias_form_inicio")
    if isinstance(session_inicio, date):
        data_inicio_ref = session_inicio.isoformat()
    elif isinstance(session_inicio, str) and session_inicio:
        data_inicio_ref = session_inicio
    disponibilidade = _cache_disponibilidade(
        data_inicio_ref or date.today().isoformat(), (("ferias_id", edit_id),) if edit_id else ()
    )
    indis = disponibilidade.get("motoristas", set()).union(disponibilidade.get("ajudantes", set()))

    colab_opts = ["Selecionar colaborador"]
    colab_map = {"Selecionar colaborador": None}
    for col in colaboradores:
        if col.get("id") in indis and col.get("id") != (edit_item.get("colaborador_id") if edit_item else None):
            continue
        label = f"{col.get('nome')} ({col.get('funcao')}) (#{col.get('id')})"
        colab_opts.append(label)
        colab_map[label] = col.get("id")

    with st.form("ferias_form"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            colab_sel = "Selecionar colaborador"
            if edit_item and edit_item.get("colaborador_id"):
                for label, cid in colab_map.items():
                    if cid == edit_item.get("colaborador_id"):
                        colab_sel = label
                        break
            colab_label = st.selectbox(
                "Colaborador",
                colab_opts,
                index=colab_opts.index(colab_sel),
                key="ferias_form_colab",
            )
            colaborador_id = colab_map.get(colab_label)
        with col_b:
            data_inicio = st.date_input(
                "Data início",
                value=_to_date(edit_item.get("data_inicio") if edit_item else date.today().isoformat()),
                key="ferias_form_inicio",
            ).isoformat()
        with col_c:
            data_fim = st.date_input(
                "Data fim",
                value=_to_date(edit_item.get("data_fim") if edit_item else date.today().isoformat()),
                key="ferias_form_fim",
            ).isoformat()
        observacao = st.text_input(
            "Observação",
            value=(edit_item.get("observacao") or "") if edit_item else "",
            key="ferias_form_obs",
        )
        submit = st.form_submit_button("Atualizar" if edit_item else "Salvar")

    if submit:
        if not colaborador_id:
            _set_flash("error", "Informe colaborador e período.")
            st.rerun()
        disponibilidade_submit = _cache_disponibilidade(
            data_inicio, (("ferias_id", edit_id),) if edit_id else ()
        )
        indis = disponibilidade_submit.get("motoristas", set()).union(
            disponibilidade_submit.get("ajudantes", set())
        )
        if colaborador_id in indis:
            _set_flash("error", "Colaborador indisponível na data de início.")
            st.rerun()
        try:
            if edit_item:
                svc.atualizar_ferias(edit_id, colaborador_id, data_inicio, data_fim, observacao or None)
                _set_flash("success", "Férias atualizadas.")
            else:
                svc.adicionar_ferias(colaborador_id, data_inicio, data_fim, observacao or None)
                _set_flash("success", "Férias salvas.")
        except Exception as exc:
            _set_flash("error", f"Erro ao salvar: {exc}")
        st.session_state["ferias_edit_id"] = None
        _clear_cached_data()
        st.rerun()

    if st.session_state.get("ferias_confirm_excluir") is not None:
        excluir_id = st.session_state.get("ferias_confirm_excluir")
        if _confirm_prompt("ferias_confirm_excluir", f"Excluir férias #{excluir_id}?"):
            try:
                svc.remover_ferias(excluir_id)
                _set_flash("success", "Férias excluídas.")
            except Exception as exc:
                _set_flash("error", f"Erro ao excluir: {exc}")
            st.session_state["ferias_edit_id"] = None
            _clear_cached_data()
            st.rerun()

    if edit_item:
        if st.button("Cancelar edição", key="ferias_cancelar"):
            st.session_state["ferias_edit_id"] = None
            st.rerun()

    if registros:
        col_sizes = [2.2, 1.2, 1.2, 2.2, 1.2, 2]
        header = st.columns(col_sizes)
        header[0].markdown('<div class="jr-head">Colaborador</div>', unsafe_allow_html=True)
        header[1].markdown('<div class="jr-head">Início</div>', unsafe_allow_html=True)
        header[2].markdown('<div class="jr-head">Fim</div>', unsafe_allow_html=True)
        header[3].markdown('<div class="jr-head">Obs</div>', unsafe_allow_html=True)
        header[4].markdown('<div class="jr-head">Status</div>', unsafe_allow_html=True)
        header[5].markdown('<div class="jr-head">Ações</div>', unsafe_allow_html=True)
        for item in registros:
            cols = st.columns(col_sizes)
            _cell(cols[0], item.get("nome") or "-")
            _cell(cols[1], item.get("data_inicio") or "-", nowrap=True)
            _cell(cols[2], item.get("data_fim") or "-", nowrap=True)
            _cell(cols[3], item.get("observacao") or "-")
            _cell(cols[4], item.get("status") or "-")
            action_cols = cols[5].columns(2)
            item_id = item.get("id")
            if action_cols[0].button(
                "Editar", key=f"ferias_row_edit_{item_id}", use_container_width=True
            ):
                st.session_state["ferias_edit_id"] = item_id
            if action_cols[1].button(
                "Excluir", key=f"ferias_row_del_{item_id}", use_container_width=True
            ):
                _request_confirm("ferias_confirm_excluir", item_id)
    else:
        st.info("Nenhum período de férias cadastrado.")


def page_colaboradores() -> None:
    st.subheader("Colaboradores")
    registros = _cache_listar_colaboradores(ativos_only=False)

    edit_id = st.session_state.get("colab_edit_id")
    edit_item = None
    if edit_id:
        edit_item = _cache_obter_colaborador_por_id(edit_id)

    with st.form("colab_form"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            nome = st.text_input(
                "Nome",
                value=(edit_item.get("nome") or "") if edit_item else "",
                key="colab_form_nome",
            )
        with col_b:
            funcao_opts = ["Motorista", "Ajudante"]
            funcao_index = funcao_opts.index(edit_item.get("funcao")) if edit_item and edit_item.get("funcao") in funcao_opts else 0
            funcao = st.selectbox(
                "Função",
                funcao_opts,
                index=funcao_index,
                key="colab_form_funcao",
            )
        with col_c:
            observacao = st.text_input(
                "Observação",
                value=(edit_item.get("observacao") or "") if edit_item else "",
                key="colab_form_obs",
            )
        ativo = st.checkbox(
            "Ativo",
            value=bool(edit_item.get("ativo")) if edit_item else True,
            key="colab_form_ativo",
        )
        submit = st.form_submit_button("Atualizar" if edit_item else "Salvar")

    if submit:
        if not nome or not funcao:
            _set_flash("error", "Informe nome e função.")
            st.rerun()
        try:
            if edit_item:
                svc.atualizar_colaborador(
                    edit_id, nome, funcao, observacao, edit_item.get("foto"), ativo
                )
                _set_flash("success", "Colaborador atualizado.")
            else:
                svc.add_colaborador(nome, funcao, observacao, None)
                _set_flash("success", "Colaborador salvo.")
        except Exception as exc:
            _set_flash("error", f"Erro ao salvar: {exc}")
        st.session_state["colab_edit_id"] = None
        _clear_cached_data()
        st.rerun()

    if st.session_state.get("colab_confirm_desativar") is not None:
        desativar_id = st.session_state.get("colab_confirm_desativar")
        if _confirm_prompt("colab_confirm_desativar", f"Desativar colaborador #{desativar_id}?"):
            try:
                svc.desativar_colaborador(desativar_id)
                _set_flash("success", "Colaborador desativado.")
            except Exception as exc:
                _set_flash("error", f"Erro ao desativar: {exc}")
            st.session_state["colab_edit_id"] = None
            _clear_cached_data()
            st.rerun()

    if st.session_state.get("colab_confirm_excluir") is not None:
        excluir_id = st.session_state.get("colab_confirm_excluir")
        if _confirm_prompt(
            "colab_confirm_excluir",
            f"Excluir colaborador #{excluir_id} e remover vínculos (folgas, férias e bloqueios)?",
        ):
            try:
                foto_path = svc.excluir_colaborador(excluir_id)
                if foto_path:
                    try:
                        (UPLOAD_DIR / foto_path).unlink()
                    except OSError:
                        pass
                _set_flash("success", "Colaborador excluído.")
            except Exception as exc:
                _set_flash("error", f"Erro ao excluir: {exc}")
            st.session_state["colab_edit_id"] = None
            _clear_cached_data()
            st.rerun()

    if edit_item:
        if st.button("Cancelar edição", key="colab_cancelar"):
            st.session_state["colab_edit_id"] = None
            st.rerun()

    if registros:
        col_sizes = [2.2, 1.2, 2.6, 1.2, 2.8]
        header = st.columns(col_sizes)
        header[0].markdown('<div class="jr-head">Nome</div>', unsafe_allow_html=True)
        header[1].markdown('<div class="jr-head">Função</div>', unsafe_allow_html=True)
        header[2].markdown('<div class="jr-head">Obs</div>', unsafe_allow_html=True)
        header[3].markdown('<div class="jr-head">Status</div>', unsafe_allow_html=True)
        header[4].markdown('<div class="jr-head">Ações</div>', unsafe_allow_html=True)
        for item in registros:
            cols = st.columns(col_sizes)
            _cell(cols[0], item.get("nome") or "-")
            _cell(cols[1], item.get("funcao") or "-")
            _cell(cols[2], item.get("observacao") or "-")
            _cell(cols[3], "Ativo" if item.get("ativo") else "Inativo", nowrap=True)
            action_cols = cols[4].columns(3)
            item_id = item.get("id")
            if action_cols[0].button(
                "Editar", key=f"colab_row_edit_{item_id}", use_container_width=True
            ):
                st.session_state["colab_edit_id"] = item_id
            if action_cols[1].button(
                "Desativar", key=f"colab_row_desativar_{item_id}", use_container_width=True
            ):
                _request_confirm("colab_confirm_desativar", item_id)
            if action_cols[2].button(
                "Excluir", key=f"colab_row_excluir_{item_id}", use_container_width=True
            ):
                _request_confirm("colab_confirm_excluir", item_id)
    else:
        st.info("Nenhum colaborador cadastrado.")


def page_log() -> None:
    st.subheader("LOG de escalas")

    col1, col2, col3 = st.columns(3)
    with col1:
        sem_inicio = st.checkbox("Sem data início", value=True, key="log_sem_inicio")
        data_inicio_val = st.date_input(
            "Data início",
            value=date.today(),
            key="log_data_inicio",
            disabled=sem_inicio,
        )
        data_inicio = None if sem_inicio else data_inicio_val.isoformat()
    with col2:
        sem_fim = st.checkbox("Sem data fim", value=True, key="log_sem_fim")
        data_fim_val = st.date_input(
            "Data fim",
            value=date.today(),
            key="log_data_fim",
            disabled=sem_fim,
        )
        data_fim = None if sem_fim else data_fim_val.isoformat()
    with col3:
        status = st.selectbox("Status", ["Em andamento", "Finalizados", "Todos"], key="log_status")

    motoristas = _cache_listar_colaboradores_por_funcao("Motorista")
    ajudantes = _cache_listar_colaboradores_por_funcao("Ajudante")
    placas = [item.get("placa") for item in _cache_listar_caminhoes(ativos_only=False)]

    col4, col5 = st.columns(2)
    with col4:
        mot_opts = ["Todos"] + [f"{m.get('nome')} (#{m.get('id')})" for m in motoristas]
        mot_map = {"Todos": None}
        for m in motoristas:
            mot_map[f"{m.get('nome')} (#{m.get('id')})"] = m.get("id")
        motorista_label = st.selectbox("Motorista", mot_opts, key="log_motorista")
        motorista_id = mot_map.get(motorista_label)
    with col5:
        placas_opts = ["Todas"] + [pl for pl in placas if pl]
        placa_label = st.selectbox("Placa", placas_opts, key="log_placa")
        placa = None if placa_label == "Todas" else placa_label

    filtros = {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "status": status,
        "motorista_id": motorista_id,
        "placa": placa,
    }

    registros = _cache_consultar_log_carregamentos(tuple(sorted(filtros.items())))

    if st.session_state.get("log_confirm_liberar") is not None:
        liberar_id = st.session_state.get("log_confirm_liberar")
        if _confirm_prompt("log_confirm_liberar", f"Liberar carregamento #{liberar_id} agora?"):
            try:
                registro = _cache_obter_carregamento(liberar_id)
                if not registro:
                    _set_flash("error", "Carregamento não encontrado.")
                    st.rerun()
                observacao_padrao = (registro.get("observacao") or "0").strip()
                duracao_planejada = svc.OBSERVACAO_DURACAO.get(observacao_padrao, 0)
                ajustes_map = svc.listar_ajustes_por_carregamentos([liberar_id])
                ajustes = ajustes_map.get(liberar_id, [])
                duracao_atual = ajustes[-1]["duracao_nova"] if ajustes else duracao_planejada
                svc.registrar_ajuste_rota(liberar_id, duracao_atual, 0, "Liberado agora")
                data_inicio_iso = svc.obter_data_saida_registro(registro)
                inicio_dt = svc.parse_date(data_inicio_iso) or date.today()
                svc.atualizar_bloqueios_para_ajuste(
                    liberar_id, inicio_dt.isoformat(), liberar_imediato=True
                )
                _set_flash("success", "Carregamento liberado.")
            except Exception as exc:
                _set_flash("error", f"Erro ao liberar: {exc}")
            _clear_cached_data()
            st.rerun()
    elif st.session_state.get("log_confirm_excluir") is not None:
        excluir_id = st.session_state.get("log_confirm_excluir")
        if _confirm_prompt("log_confirm_excluir", f"Excluir carregamento #{excluir_id}?"):
            try:
                svc.remover_carregamento_completo(excluir_id)
                _set_flash("success", "Carregamento excluído.")
            except Exception as exc:
                _set_flash("error", f"Erro ao excluir: {exc}")
            _clear_cached_data()
            st.rerun()

    if st.button("Exportar Excel", key="log_exportar"):
        caminho = exportar_log_para_excel(registros)
        if caminho.exists():
            st.download_button(
                "Baixar Excel",
                data=caminho.read_bytes(),
                file_name=caminho.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="log_exportar_download",
            )

    if not registros:
        st.info("Nenhum registro encontrado para os filtros.")
        return

    for item in registros:
        with st.container():
            st.markdown(f"**{item.get('data_br')}** - {item.get('rota')} - {item.get('placa')}")
            st.write(f"{item.get('motorista')} | {item.get('ajudante')}")
            st.write(f"Status: {item.get('status')} {item.get('status_texto')}")
            st.write(f"Saída: {item.get('data_saida_br')} | Previsto: {item.get('data_fim_br')}")
            st.write(
                f"Planejado: {item.get('duracao_planejada')} | Efetivo: {item.get('duracao_efetiva')}"
            )
            st.write(f"Resumo: {item.get('resumo')}")

            with st.form(f"log_colab_{item['id']}"):
                mot_opts = [svc.VALOR_SEM_MOTORISTA] + [
                    f"{m.get('nome')} (#{m.get('id')})" for m in motoristas
                ]
                mot_map = {svc.VALOR_SEM_MOTORISTA: None}
                for m in motoristas:
                    mot_map[f"{m.get('nome')} (#{m.get('id')})"] = m.get("id")
                mot_sel = svc.VALOR_SEM_MOTORISTA
                if item.get("motorista_id"):
                    for label, mid in mot_map.items():
                        if mid == item.get("motorista_id"):
                            mot_sel = label
                            break
                motorista_label = st.selectbox(
                    "Motorista",
                    mot_opts,
                    index=mot_opts.index(mot_sel),
                    key=f"log_motorista_{item['id']}",
                )
                aju_opts = [svc.VALOR_SEM_AJUDANTE] + [
                    f"{a.get('nome')} (#{a.get('id')})" for a in ajudantes
                ]
                aju_map = {svc.VALOR_SEM_AJUDANTE: None}
                for a in ajudantes:
                    aju_map[f"{a.get('nome')} (#{a.get('id')})"] = a.get("id")
                aju_sel = svc.VALOR_SEM_AJUDANTE
                if item.get("ajudante_id"):
                    for label, aid in aju_map.items():
                        if aid == item.get("ajudante_id"):
                            aju_sel = label
                            break
                ajudante_label = st.selectbox(
                    "Ajudante",
                    aju_opts,
                    index=aju_opts.index(aju_sel),
                    key=f"log_ajudante_{item['id']}",
                )
                atualizar = st.form_submit_button("Atualizar colaboradores")
                if atualizar:
                    motorista_id = mot_map.get(motorista_label)
                    ajudante_id = aju_map.get(ajudante_label)
                    if motorista_id and ajudante_id and motorista_id == ajudante_id:
                        _set_flash("error", "Motorista e ajudante devem ser pessoas diferentes.")
                        st.rerun()
                    registro = _cache_obter_carregamento(item["id"])
                    if not registro:
                        _set_flash("error", "Carregamento não encontrado.")
                        st.rerun()
                    data_base_iso = svc.obter_data_saida_registro(registro)
                    disponibilidade = _cache_disponibilidade(
                        data_base_iso, (("carregamento_id", item["id"]),)
                    )
                    indis = disponibilidade.get("motoristas", set()).union(
                        disponibilidade.get("ajudantes", set())
                    )
                    if motorista_id and motorista_id in indis:
                        _set_flash("error", "Motorista indisponível nesta data.")
                        st.rerun()
                    if ajudante_id and ajudante_id in indis:
                        _set_flash("error", "Ajudante indisponível nesta data.")
                        st.rerun()
                    try:
                        observacao = (registro.get("observacao") or "0").strip() or "0"
                        svc.atualizar_carregamento(
                            item["id"],
                            registro.get("data") or date.today().isoformat(),
                            registro.get("data_saida"),
                            registro.get("rota") or "",
                            registro.get("placa"),
                            motorista_id,
                            ajudante_id,
                            observacao,
                            registro.get("observacao_extra"),
                            registro.get("observacao_cor"),
                        )
                        svc.remover_bloqueios_por_carregamento(item["id"])
                        svc.criar_bloqueios_para_carregamento(
                            item["id"],
                            registro.get("data") or date.today().isoformat(),
                            [motorista_id, ajudante_id],
                            observacao,
                        )
                        _set_flash("success", "Colaboradores atualizados.")
                    except Exception as exc:
                        _set_flash("error", f"Erro ao atualizar colaboradores: {exc}")
                    _clear_cached_data()
                    st.rerun()

            with st.form(f"log_ajuste_{item['id']}"):
                duracao_nova = st.number_input(
                    "Nova duração (dias)",
                    min_value=-1,
                    step=1,
                    value=0,
                    key=f"log_duracao_{item['id']}",
                )
                observacao = st.text_input(
                    "Obs. ajuste",
                    key=f"log_obs_{item['id']}",
                )
                ajustar = st.form_submit_button("Registrar ajuste")
                if ajustar:
                    try:
                        registro = _cache_obter_carregamento(item["id"])
                        if not registro:
                            _set_flash("error", "Carregamento não encontrado.")
                            st.rerun()
                        observacao_padrao = (registro.get("observacao") or "0").strip()
                        duracao_planejada = svc.OBSERVACAO_DURACAO.get(observacao_padrao, 0)
                        ajustes_map = svc.listar_ajustes_por_carregamentos([item["id"]])
                        ajustes = ajustes_map.get(item["id"], [])
                        duracao_atual = ajustes[-1]["duracao_nova"] if ajustes else duracao_planejada
                        svc.registrar_ajuste_rota(item["id"], duracao_atual, int(duracao_nova), observacao)
                        data_inicio_iso = svc.obter_data_saida_registro(registro)
                        inicio_dt = svc.parse_date(data_inicio_iso) or date.today()
                        nova_data_fim = inicio_dt + timedelta(days=int(duracao_nova))
                        svc.atualizar_bloqueios_para_ajuste(
                            item["id"], nova_data_fim.isoformat(), False
                        )
                        _set_flash("success", "Ajuste registrado.")
                    except Exception as exc:
                        _set_flash("error", f"Erro ao registrar ajuste: {exc}")
                    _clear_cached_data()
                    st.rerun()

            action_cols = st.columns(2)
            if item.get("status") != "Finalizado":
                if action_cols[0].button("Liberar agora", key=f"log_liberar_{item['id']}"):
                    _request_confirm("log_confirm_liberar", item["id"])
            if action_cols[1].button("Excluir carregamento", key=f"log_excluir_{item['id']}"):
                _request_confirm("log_confirm_excluir", item["id"])
        st.markdown("---")


def main() -> None:
    st.set_page_config(page_title="JR Escala", layout="wide")
    _init_database_once()
    _init_state()
    _inject_css()
    _render_topbar()
    _render_flash()
    _assistentes_sidebar(st.session_state.get("carreg_data_iso", date.today().isoformat()))

    pagina = st.radio(
        "Navegação",
        NAV_ITEMS,
        horizontal=True,
        label_visibility="collapsed",
        key="nav_page",
    )

    if pagina == "Carregamentos":
        page_carregamentos()
    elif pagina == "Escala (CD)":
        page_escala_cd()
    elif pagina == "Folgas":
        page_folgas()
    elif pagina == "Oficinas":
        page_oficinas()
    elif pagina == "Rotas Semanais":
        page_rotas_semanais()
    elif pagina == "Caminhões":
        page_caminhoes()
    elif pagina == "Férias":
        page_ferias()
    elif pagina == "Colaboradores":
        page_colaboradores()
    elif pagina == "LOG":
        page_log()


if __name__ == "__main__":
    main()
