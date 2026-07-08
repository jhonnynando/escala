from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
import os
import re

from PIL import Image, ImageOps

from .db import DBError, UPLOAD_DIR, get_connection, insert_and_get_id

COR_AZUL = "#1B5FAF"
COR_AZUL_CLARO = "#1990FF"
COR_AZUL_HOVER = "#0E75D0"
COR_AZUL_GRADIENTE_FIM = "#4A8EDB"
COR_VERMELHA = "#C8102E"
COR_VERMELHA_HOVER = "#A30D26"
COR_FUNDO = "#F5F6FA"
COR_TEXTO = "#1c1c1c"
COR_PAINEL = "#FFFFFF"
COR_CINZA = "#D6DEE9"
COR_NEUTRO = "#9BA7BA"
EMPTY_STATE_COLOR = "#6B7280"
CARD_BG_DEFAULT = "#FFFFFF"
CARD_BG_ALT = "#F0F4FF"
CARD_BG_EDICAO = "#E6EEFF"
BORDER_COR = "#E0E6EF"
NAV_BG = "#0D4A92"
NAV_PILL = "#1D4C85"
NAV_PILL_HOVER = "#2B64A7"
DEFAULT_EMPTY_MESSAGE = "Nenhum registro encontrado."
DISPLAY_VAZIO = "-"
VALOR_SEM_MOTORISTA = "Sem motorista"
VALOR_SEM_AJUDANTE = "Sem ajudante"
VALOR_SEM_CAMINHAO = "Sem caminhão"
MOTORISTA_AJUDANTE_TAG = "(.mot)"
AVISO_NENHUM_COLAB = "Nenhum colaborador disponível para este dia."

OBSERVACAO_OPCOES = [
    "0",
    "ROTA 1 DIA (BATE E VOLTA)",
    "ROTA 2 DIAS",
    "ROTA 3 DIAS",
    "ROTA 4 DIAS",
    "ROTA 5 DIAS",
]

OBSERVACAO_DURACAO = {
    "0": 0,
    "ROTA 1 DIA (BATE E VOLTA)": 0,
    "ROTA 2 DIAS": 1,
    "ROTA 3 DIAS": 2,
    "ROTA 4 DIAS": 3,
    "ROTA 5 DIAS": 4,
}

OBS_MARCADORES = [
    ("Sem cor", ""),
    ("Amarelo", "#FFF59D"),
    ("Verde", "#C8E6C9"),
    ("Azul", "#BBDEFB"),
    ("Vermelho", "#FFCDD2"),
    ("Laranja", "#FFE0B2"),
]
OBS_MARCADORES_MAP = {label: cor for label, cor in OBS_MARCADORES}

DIAS_SEMANA = [
    ("segunda", "Segunda"),
    ("terca", "Terça"),
    ("quarta", "Quarta"),
    ("quinta", "Quinta"),
    ("sexta", "Sexta"),
    ("sabado", "Sábado"),
    ("domingo", "Domingo"),
]

DIAS_EXTENSO = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

MESES_EXTENSO = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


def combinar_observacoes(observacao_padrao: str | None, observacao_extra: str | None) -> str:
    padrao = (observacao_padrao or "").strip()
    extra = (observacao_extra or "").strip()
    if padrao.lower() in ("none", "null"):
        padrao = ""
    if extra.lower() in ("none", "null"):
        extra = ""
    if padrao and extra:
        return f"{padrao} - {extra}"
    if padrao:
        return padrao
    if extra:
        return extra
    return DISPLAY_VAZIO


def _safe_fetch(cur, query: str, params: Iterable[Any] = ()):
    cur.execute(query, tuple(params))
    return cur.fetchall()


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def data_iso_para_extenso(data_iso: str | None) -> str:
    if not data_iso:
        return DISPLAY_VAZIO
    try:
        data_dt = datetime.strptime(data_iso, "%Y-%m-%d").date()
    except ValueError:
        return data_iso
    nome_dia = DIAS_EXTENSO[data_dt.weekday()]
    nome_mes = MESES_EXTENSO[data_dt.month - 1]
    return f"{nome_dia}, {data_dt.day:02d} de {nome_mes} de {data_dt.year}"


def data_iso_para_br(data_iso: str | None) -> str:
    if not data_iso:
        return DISPLAY_VAZIO
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return data_iso


def data_br_para_iso(data_br: str | None) -> str | None:
    if not data_br:
        return None
    try:
        return datetime.strptime(data_br.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def data_iso_para_br_entrada(data_iso: str | None) -> str:
    if not data_iso:
        return ""
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return data_iso


def dias_para_texto(valor: int) -> str:
    sufixo = "dia" if abs(valor) == 1 else "dias"
    return f"{valor} {sufixo}"


def calcular_data_saida_padrao(data_iso: str | None) -> str | None:
    if not data_iso:
        return None
    try:
        base = datetime.strptime(data_iso, "%Y-%m-%d").date()
    except ValueError:
        return None
    dias = 3 if base.weekday() == 4 else 1
    return (base + timedelta(days=dias)).isoformat()


def calcular_data_saida_carregamento(data_iso: str | None) -> str | None:
    return calcular_data_saida_padrao(data_iso)


def normalizar_cor_hex(cor: str | None) -> str | None:
    if not cor:
        return None
    cor = cor.strip()
    if not cor:
        return None
    if not cor.startswith("#"):
        return cor.upper()
    if len(cor) == 4:
        r, g, b = cor[1], cor[2], cor[3]
        cor = f"#{r}{r}{g}{g}{b}{b}"
    return cor.upper()


def label_cor_observacao(cor_hex: str | None) -> str:
    cor_norm = normalizar_cor_hex(cor_hex)
    for label, cor in OBS_MARCADORES:
        if cor_norm == normalizar_cor_hex(cor):
            return label
    return OBS_MARCADORES[0][0]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def ajustar_tom(hex_color: str, fator: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    r = max(0, min(255, int(r * fator)))
    g = max(0, min(255, int(g * fator)))
    b = max(0, min(255, int(b * fator)))
    return _rgb_to_hex((r, g, b))


def ajustar_cor_marcador(cor_hex: str | None) -> str | None:
    cor_norm = normalizar_cor_hex(cor_hex)
    if not cor_norm:
        return None
    return ajustar_tom(cor_norm, 1.02)


def normalizar_dia_semana(valor: str | None) -> str:
    if not valor:
        return DIAS_SEMANA[0][0]
    valor = valor.strip().lower()
    for chave, label in DIAS_SEMANA:
        if valor.startswith(chave[:3]) or valor.startswith(chave) or valor.startswith(label.lower()[:3]):
            return chave
    return DIAS_SEMANA[0][0]


def obter_dia_semana_por_data(data_iso: str) -> str:
    try:
        dt = datetime.strptime(data_iso, "%Y-%m-%d")
    except ValueError:
        return DIAS_SEMANA[0][0]
    idx = dt.weekday() % len(DIAS_SEMANA)
    return DIAS_SEMANA[idx][0]

# Disponibilidade


def verificar_disponibilidade(data_iso: str, ignorar: dict[str, int] | None = None) -> dict[str, set[Any]]:
    resultado: dict[str, set[Any]] = {
        "motoristas": set(),
        "ajudantes": set(),
        "caminhoes": set(),
    }
    data_iso = (data_iso or "").strip()
    alvo = parse_date(data_iso)
    if not alvo:
        return resultado

    ignorar = ignorar or {}
    janela_inicio = (alvo - timedelta(days=14)).isoformat()
    janela_fim = alvo.isoformat()

    with get_connection() as conn:
        cur = conn.cursor()

        ajustes_atuais: dict[int, int] = {}
        for car_id, duracao_nova in _safe_fetch(
            cur,
            """
            SELECT a.carregamento_id, a.duracao_nova
            FROM ajustes_rotas a
            INNER JOIN (
                SELECT carregamento_id, MAX(id) AS max_id
                FROM ajustes_rotas
                GROUP BY carregamento_id
            ) ult
            ON ult.carregamento_id = a.carregamento_id
            AND ult.max_id = a.id
            """,
        ):
            ajustes_atuais[car_id] = duracao_nova

        for ferias_id, col_id, inicio, fim in _safe_fetch(
            cur,
            """
            SELECT id, colaborador_id, data_inicio, data_fim
            FROM ferias
            WHERE data_inicio <= ? AND data_fim >= ?
            """,
            (data_iso, data_iso),
        ):
            if not col_id or ignorar.get("ferias_id") == ferias_id:
                continue
            d_inicio = parse_date(inicio)
            d_fim = parse_date(fim)
            if d_inicio and d_fim and d_inicio <= alvo <= d_fim:
                resultado["motoristas"].add(col_id)
                resultado["ajudantes"].add(col_id)

        for folga_id, col_id in _safe_fetch(
            cur,
            "SELECT id, colaborador_id FROM folgas WHERE data = ?",
            (data_iso,),
        ):
            if not col_id or ignorar.get("folga_id") == folga_id:
                continue
            resultado["motoristas"].add(col_id)
            resultado["ajudantes"].add(col_id)

        for ofi_id, mot_id, placa in _safe_fetch(
            cur,
            "SELECT id, motorista_id, placa FROM oficinas WHERE data = ?",
            (data_iso,),
        ):
            if ignorar.get("oficina_id") == ofi_id:
                continue
            if mot_id:
                resultado["motoristas"].add(mot_id)
                resultado["ajudantes"].add(mot_id)
            if placa:
                resultado["caminhoes"].add(placa.upper())

        for escala_id, mot_id, aju_id in _safe_fetch(
            cur,
            "SELECT id, motorista_id, ajudante_id FROM escala_cd WHERE data = ?",
            (data_iso,),
        ):
            if ignorar.get("escala_cd_id") == escala_id:
                continue
            if mot_id:
                resultado["motoristas"].add(mot_id)
                resultado["ajudantes"].add(mot_id)
            if aju_id:
                resultado["ajudantes"].add(aju_id)
                resultado["motoristas"].add(aju_id)

        for _, col_id, inicio, fim, car_id in _safe_fetch(
            cur,
            """
            SELECT id, colaborador_id, data_inicio, data_fim, carregamento_id
            FROM bloqueios
            WHERE data_inicio <= ? AND data_fim >= ?
            """,
            (data_iso, data_iso),
        ):
            if not col_id:
                continue
            if car_id:
                if ignorar.get("carregamento_id") == car_id:
                    continue
                continue
            d_inicio = parse_date(inicio)
            d_fim = parse_date(fim)
            if d_inicio and d_fim and d_inicio <= alvo < d_fim:
                resultado["motoristas"].add(col_id)
                resultado["ajudantes"].add(col_id)

        for (
            car_id,
            data_registro,
            data_saida,
            mot_id,
            aju_id,
            placa,
            observacao,
        ) in _safe_fetch(
            cur,
            """
            SELECT id, data, data_saida, motorista_id, ajudante_id, placa, observacao
            FROM carregamentos
            WHERE data = ?
               OR (data >= ? AND data <= ?)
               OR (data_saida IS NOT NULL AND data_saida >= ? AND data_saida <= ?)
            """,
            (data_iso, janela_inicio, janela_fim, janela_inicio, janela_fim),
        ):
            if ignorar.get("carregamento_id") == car_id:
                continue
            data_registro_dt = parse_date(data_registro)
            data_saida_dt = parse_date(data_saida)
            if not data_registro_dt and not data_saida_dt:
                continue
            if not data_registro_dt:
                data_registro_dt = data_saida_dt
            if not data_saida_dt and data_registro_dt:
                dias_padrao = 3 if data_registro_dt.weekday() == 4 else 1
                data_saida_dt = data_registro_dt + timedelta(days=dias_padrao)
            if data_saida_dt and data_registro_dt and data_saida_dt < data_registro_dt:
                data_saida_dt = data_registro_dt
            dias = ajustes_atuais.get(
                car_id, OBSERVACAO_DURACAO.get((observacao or "").strip(), 0)
            )
            if dias < 0:
                continue
            duracao_dias = max(dias, 0)
            bloquear_registro = data_registro_dt == alvo if data_registro_dt else False
            bloquear_viagem = False
            if duracao_dias > 0:
                inicio_viagem = data_saida_dt or data_registro_dt
                if inicio_viagem:
                    fim_viagem = inicio_viagem + timedelta(days=duracao_dias)
                    bloquear_viagem = inicio_viagem <= alvo < fim_viagem
            if bloquear_registro or bloquear_viagem:
                if mot_id:
                    resultado["motoristas"].add(mot_id)
                    resultado["ajudantes"].add(mot_id)
                if aju_id:
                    resultado["ajudantes"].add(aju_id)
                    resultado["motoristas"].add(aju_id)
                if placa:
                    resultado["caminhoes"].add(placa.upper())

    return resultado


# Colaboradores


def add_colaborador(nome: str, funcao: str, observacao: str = "", foto: str | None = None) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        novo_id = insert_and_get_id(
            cur,
            "INSERT INTO colaboradores (nome, funcao, observacao, foto, ativo) VALUES (?, ?, ?, ?, 1);",
            (nome.strip(), funcao.strip(), observacao.strip(), foto or ""),
        )
        conn.commit()
        return novo_id


def listar_colaboradores(ativos_only: bool = False) -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        if ativos_only:
            cur.execute(
                "SELECT id, nome, funcao, observacao, foto, ativo FROM colaboradores WHERE ativo = 1 ORDER BY nome;"
            )
        else:
            cur.execute(
                "SELECT id, nome, funcao, observacao, foto, ativo FROM colaboradores ORDER BY ativo DESC, nome;"
            )
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["foto"] = row.get("foto") or None
    return rows


def obter_colaborador_por_id(colaborador_id: int | None) -> dict | None:
    if not colaborador_id:
        return None
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, funcao, observacao, foto, ativo FROM colaboradores WHERE id = ?;",
            (colaborador_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def atualizar_colaborador(
    colaborador_id: int,
    nome: str,
    funcao: str,
    observacao: str,
    foto: str | None,
    ativo: bool = True,
) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE colaboradores
            SET nome = ?, funcao = ?, observacao = ?, foto = ?, ativo = ?
            WHERE id = ?;
            """,
            (nome.strip(), funcao.strip(), observacao.strip(), foto or "", 1 if ativo else 0, colaborador_id),
        )
        conn.commit()


def desativar_colaborador(colaborador_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE colaboradores SET ativo = 0 WHERE id = ?;", (colaborador_id,))
        conn.commit()


def excluir_colaborador(colaborador_id: int) -> str | None:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT foto FROM colaboradores WHERE id = ?;", (colaborador_id,))
        row = cur.fetchone()
        foto = row["foto"] if row else None
        cur.execute("DELETE FROM folgas WHERE colaborador_id = ?;", (colaborador_id,))
        cur.execute("DELETE FROM ferias WHERE colaborador_id = ?;", (colaborador_id,))
        cur.execute("DELETE FROM bloqueios WHERE colaborador_id = ?;", (colaborador_id,))
        cur.execute("UPDATE carregamentos SET motorista_id = NULL WHERE motorista_id = ?;", (colaborador_id,))
        cur.execute("UPDATE carregamentos SET ajudante_id = NULL WHERE ajudante_id = ?;", (colaborador_id,))
        cur.execute("UPDATE escala_cd SET motorista_id = NULL WHERE motorista_id = ?;", (colaborador_id,))
        cur.execute("UPDATE escala_cd SET ajudante_id = NULL WHERE ajudante_id = ?;", (colaborador_id,))
        cur.execute("UPDATE oficinas SET motorista_id = NULL WHERE motorista_id = ?;", (colaborador_id,))
        cur.execute("DELETE FROM colaboradores WHERE id = ?;", (colaborador_id,))
        conn.commit()
        return foto or None


def listar_colaboradores_por_funcao(
    funcao: str,
    data_iso: str | None = None,
    ignorar: dict[str, int] | None = None,
) -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, nome, funcao, observacao, foto
            FROM colaboradores
            WHERE ativo = 1 AND lower(funcao) = ?
            ORDER BY nome;
            """,
            (funcao.lower(),),
        )
        colaboradores = []
        for row in cur.fetchall():
            dados = dict(row)
            dados["foto"] = dados.get("foto") or None
            colaboradores.append(dados)

    if not data_iso:
        return colaboradores

    chave = "motoristas" if funcao.lower().startswith("motor") else "ajudantes"
    indisponiveis = verificar_disponibilidade(data_iso, ignorar).get(chave, set())
    return [col for col in colaboradores if col["id"] not in indisponiveis]


def formatar_ajudante_nome(nome: str, colaborador_id: int | None) -> str:
    if not colaborador_id:
        return nome
    if not nome or nome == DISPLAY_VAZIO:
        return nome or DISPLAY_VAZIO
    dados = obter_colaborador_por_id(colaborador_id)
    if not dados:
        return nome
    funcao = (dados.get("funcao") or "").lower()
    if funcao.startswith("motor") and MOTORISTA_AJUDANTE_TAG not in nome:
        return f"{nome} {MOTORISTA_AJUDANTE_TAG}"
    return nome


# Fotos


def salvar_foto_colaborador(file_bytes: bytes, filename: str) -> str | None:
    if not file_bytes:
        return None
    max_bytes = 100 * 1024
    max_dim = 512
    try:
        imagem = Image.open(BytesIO(file_bytes))
        imagem = ImageOps.exif_transpose(imagem)
        if imagem.mode in ("RGBA", "LA"):
            fundo = Image.new("RGB", imagem.size, (255, 255, 255))
            fundo.paste(imagem, mask=imagem.split()[-1])
            imagem = fundo
        else:
            imagem = imagem.convert("RGB")
        if max(imagem.size) > max_dim:
            imagem.thumbnail((max_dim, max_dim), Image.LANCZOS)

        foto_bytes = None
        qualidades = (85, 80, 75, 70, 65, 60, 55, 50, 45)
        for qualidade in qualidades:
            buffer = BytesIO()
            imagem.save(
                buffer,
                format="JPEG",
                quality=qualidade,
                optimize=True,
                progressive=True,
                subsampling=2,
            )
            data = buffer.getvalue()
            if len(data) <= max_bytes:
                foto_bytes = data
                break

        if foto_bytes is None:
            trabalho = imagem
            while max(trabalho.size) > 128 and foto_bytes is None:
                trabalho = trabalho.resize(
                    (max(1, int(trabalho.size[0] * 0.85)), max(1, int(trabalho.size[1] * 0.85))),
                    Image.LANCZOS,
                )
                for qualidade in (60, 50, 45, 40, 35):
                    buffer = BytesIO()
                    trabalho.save(
                        buffer,
                        format="JPEG",
                        quality=qualidade,
                        optimize=True,
                        progressive=True,
                        subsampling=2,
                    )
                    data = buffer.getvalue()
                    if len(data) <= max_bytes:
                        foto_bytes = data
                        break

        if foto_bytes is None:
            buffer = BytesIO()
            imagem.save(
                buffer,
                format="JPEG",
                quality=30,
                optimize=True,
                progressive=True,
                subsampling=2,
            )
            foto_bytes = buffer.getvalue()
        if len(foto_bytes) > max_bytes:
            raise ValueError("Imagem muito grande para salvar.")
    except Exception as exc:
        raise ValueError("Falha ao processar a imagem.") from exc
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".jpg"
    safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}{ext}"
    destino = UPLOAD_DIR / safe_name
    destino.write_bytes(foto_bytes)
    return destino.relative_to(UPLOAD_DIR).as_posix()

# Caminhões


def add_caminhao(placa: str, modelo: str, observacao: str) -> int:
    placa_db = (placa or "").strip().upper()
    with get_connection() as conn:
        cur = conn.cursor()
        novo_id = insert_and_get_id(
            cur,
            "INSERT INTO caminhoes (placa, modelo, observacao, ativo) VALUES (?, ?, ?, 1);",
            (placa_db, (modelo or "").strip(), (observacao or "").strip()),
        )
        conn.commit()
        return novo_id


def listar_caminhoes(ativos_only: bool = True) -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        if ativos_only:
            cur.execute(
                "SELECT id, placa, modelo, observacao, ativo FROM caminhoes WHERE ativo = 1 ORDER BY placa;"
            )
        else:
            cur.execute(
                "SELECT id, placa, modelo, observacao, ativo FROM caminhoes ORDER BY ativo DESC, placa;"
            )
        return [dict(row) for row in cur.fetchall()]


def editar_caminhao(caminhao_id: int, placa: str, modelo: str, observacao: str, ativo: bool = True) -> None:
    placa_db = (placa or "").strip().upper()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE caminhoes
            SET placa = ?, modelo = ?, observacao = ?, ativo = ?
            WHERE id = ?;
            """,
            (placa_db, (modelo or "").strip(), (observacao or "").strip(), 1 if ativo else 0, caminhao_id),
        )
        conn.commit()


def remover_caminhao(caminhao_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM caminhoes WHERE id = ?;", (caminhao_id,))
        conn.commit()


def listar_caminhoes_ativos() -> list[dict]:
    return listar_caminhoes(ativos_only=True)


def placa_em_manutencao(placa: str, data_iso: str) -> bool:
    if not placa:
        return False
    indisponiveis = verificar_disponibilidade(data_iso).get("caminhoes", set())
    return placa.upper() in indisponiveis


# Folgas


def salvar_folga(
    data_inicio: str,
    colaborador_id: int,
    data_fim: str | None = None,
    data_saida: str | None = None,
    observacao_padrao: str | None = None,
    observacao_extra: str | None = None,
    observacao_cor: str | None = None,
) -> int:
    data_fim = data_fim or None
    data_saida = data_saida or None
    with get_connection() as conn:
        cur = conn.cursor()
        novo_id = insert_and_get_id(
            cur,
            """
            INSERT INTO folgas (data, data_fim, data_saida, colaborador_id, observacao_padrao, observacao_extra, observacao_cor)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                data_inicio,
                data_fim,
                data_saida,
                colaborador_id,
                observacao_padrao,
                observacao_extra,
                observacao_cor,
            ),
        )
        conn.commit()
        return novo_id


def listar_folgas(data_iso: str) -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                f.id AS folga_id,
                c.id AS colaborador_id,
                c.nome,
                c.funcao,
                f.data,
                f.data_fim,
                f.data_saida,
                f.observacao_padrao,
                f.observacao_extra,
                f.observacao_cor
            FROM folgas f
            INNER JOIN colaboradores c ON c.id = f.colaborador_id
            WHERE f.data = ?
            ORDER BY c.nome;
            """,
            (data_iso,),
        )
        return [dict(row) for row in cur.fetchall()]


def listar_folgas_por_data_saida(data_iso: str) -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                f.id AS folga_id,
                c.id AS colaborador_id,
                c.nome,
                c.funcao,
                f.data,
                f.data_fim,
                f.data_saida,
                f.observacao_padrao,
                f.observacao_extra,
                f.observacao_cor
            FROM folgas f
            INNER JOIN colaboradores c ON c.id = f.colaborador_id
            WHERE COALESCE(f.data_saida, f.data) = ?
            ORDER BY c.nome;
            """,
            (data_iso,),
        )
        return [dict(row) for row in cur.fetchall()]


def editar_folga(
    folga_id: int,
    data_inicio: str,
    data_fim: str | None,
    data_saida: str | None,
    colaborador_id: int,
    observacao_padrao: str | None,
    observacao_extra: str | None,
    observacao_cor: str | None,
) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE folgas
            SET
                data = ?,
                data_fim = ?,
                data_saida = ?,
                colaborador_id = ?,
                observacao_padrao = ?,
                observacao_extra = ?,
                observacao_cor = ?
            WHERE id = ?;
            """,
            (
                data_inicio,
                data_fim,
                data_saida,
                colaborador_id,
                observacao_padrao,
                observacao_extra,
                observacao_cor,
                folga_id,
            ),
        )
        conn.commit()


def remover_folga(folga_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM folgas WHERE id = ?;", (folga_id,))
        conn.commit()

# Férias


def validar_periodo(data_inicio: str, data_fim: str) -> None:
    dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
    dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
    if dt_inicio > dt_fim:
        raise ValueError("Data inicial não pode ser posterior à data final.")


def adicionar_ferias(colaborador_id: int, data_inicio: str, data_fim: str, observacao: str | None) -> int:
    validar_periodo(data_inicio, data_fim)
    observacao_db = (observacao or "").strip() or None
    with get_connection() as conn:
        cur = conn.cursor()
        novo_id = insert_and_get_id(
            cur,
            """
            INSERT INTO ferias (colaborador_id, data_inicio, data_fim, observacao)
            VALUES (?, ?, ?, ?);
            """,
            (colaborador_id, data_inicio, data_fim, observacao_db),
        )
        conn.commit()
        return novo_id


def atualizar_ferias(registro_id: int, colaborador_id: int, data_inicio: str, data_fim: str, observacao: str | None) -> None:
    validar_periodo(data_inicio, data_fim)
    observacao_db = (observacao or "").strip() or None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE ferias
            SET colaborador_id = ?, data_inicio = ?, data_fim = ?, observacao = ?
            WHERE id = ?;
            """,
            (colaborador_id, data_inicio, data_fim, observacao_db, registro_id),
        )
        conn.commit()


def remover_ferias(registro_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ferias WHERE id = ?;", (registro_id,))
        conn.commit()


def listar_ferias() -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT f.id,
                   f.colaborador_id,
                   c.nome,
                   c.foto,
                   f.data_inicio,
                   f.data_fim,
                   f.observacao
            FROM ferias f
            INNER JOIN colaboradores c ON c.id = f.colaborador_id
            ORDER BY f.data_inicio DESC, c.nome;
            """
        )
        registros = [dict(row) for row in cur.fetchall()]
    hoje = date.today()
    for item in registros:
        fim = parse_date(item.get("data_fim"))
        if fim and fim < hoje:
            item["status"] = "Finalizada"
            item["status_class"] = "ok"
        else:
            item["status"] = "Em andamento"
            item["status_class"] = "warn"
    return registros

# Bloqueios


def remover_bloqueios_por_carregamento(carregamento_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM bloqueios WHERE carregamento_id = ?;", (carregamento_id,))
        conn.commit()


def criar_bloqueios_para_carregamento(
    carregamento_id: int,
    data_iso: str,
    colaborador_ids: list[int | None],
    observacao: str,
) -> None:
    dias = OBSERVACAO_DURACAO.get(observacao, 0)
    data_inicio = datetime.strptime(data_iso, "%Y-%m-%d").date()
    data_fim = data_inicio + timedelta(days=dias)
    with get_connection() as conn:
        cur = conn.cursor()
        for colaborador_id in colaborador_ids:
            if not colaborador_id:
                continue
            cur.execute(
                """
                INSERT INTO bloqueios (colaborador_id, data_inicio, data_fim, motivo, carregamento_id)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    colaborador_id,
                    data_inicio.isoformat(),
                    data_fim.isoformat(),
                    observacao,
                    carregamento_id,
                ),
            )
        conn.commit()


def limpar_bloqueios_expirados() -> None:
    hoje = date.today().isoformat()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM bloqueios WHERE data_fim <= ?;", (hoje,))
        conn.commit()


# Carregamentos


def salvar_carregamento(
    data_iso: str,
    rota_texto: str,
    placa: str | None,
    motorista_id: int | None,
    ajudante_id: int | None,
    observacao: str,
    observacao_extra: str | None = None,
    observacao_cor: str | None = None,
    data_saida: str | None = None,
    revisado: bool = False,
) -> int:
    if motorista_id and ajudante_id and motorista_id == ajudante_id:
        raise ValueError("Motorista e ajudante devem ser pessoas diferentes.")

    placa_db = placa.strip().upper() if placa else None
    observacao_db = observacao.strip() if observacao else None
    observacao_extra_db = observacao_extra.strip() if observacao_extra else None
    observacao_cor_db = observacao_cor.strip() if observacao_cor else None
    data_saida_db = data_saida or calcular_data_saida_carregamento(data_iso) or data_iso
    revisado_db = 1 if revisado else 0

    with get_connection() as conn:
        cur = conn.cursor()
        novo_id = insert_and_get_id(
            cur,
            """
            INSERT INTO carregamentos (
                data,
                data_saida,
                rota,
                placa,
                motorista_id,
                ajudante_id,
                observacao,
                observacao_extra,
                observacao_cor,
                revisado
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                data_iso,
                data_saida_db,
                rota_texto,
                placa_db,
                motorista_id,
                ajudante_id,
                observacao_db,
                observacao_extra_db,
                observacao_cor_db,
                revisado_db,
            ),
        )
        conn.commit()
        return novo_id


def atualizar_carregamento(
    carregamento_id: int,
    data_iso: str,
    data_saida: str | None,
    rota_texto: str,
    placa: str | None,
    motorista_id: int | None,
    ajudante_id: int | None,
    observacao: str,
    observacao_extra: str | None = None,
    observacao_cor: str | None = None,
) -> None:
    placa_db = placa.strip().upper() if placa else None
    observacao_db = observacao.strip() if observacao else None
    observacao_extra_db = observacao_extra.strip() if observacao_extra else None
    observacao_cor_db = observacao_cor.strip() if observacao_cor else None
    data_saida_db = data_saida or calcular_data_saida_carregamento(data_iso) or data_iso
    revisado_db = 1
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE carregamentos
            SET data = ?,
                data_saida = ?,
                rota = ?,
                placa = ?,
                motorista_id = ?,
                ajudante_id = ?,
                observacao = ?,
                observacao_extra = ?,
                observacao_cor = ?,
                revisado = ?
            WHERE id = ?;
            """,
            (
                data_iso,
                data_saida_db,
                rota_texto,
                placa_db,
                motorista_id,
                ajudante_id,
                observacao_db,
                observacao_extra_db,
                observacao_cor_db,
                revisado_db,
                carregamento_id,
            ),
        )
        conn.commit()


def remover_carregamento(carregamento_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM carregamentos WHERE id = ?;", (carregamento_id,))
        conn.commit()


def remover_carregamento_completo(carregamento_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM bloqueios WHERE carregamento_id = ?;", (carregamento_id,))
        cur.execute("DELETE FROM ajustes_rotas WHERE carregamento_id = ?;", (carregamento_id,))
        cur.execute("DELETE FROM carregamentos WHERE id = ?;", (carregamento_id,))
        conn.commit()


def listar_carregamentos(data_iso: str) -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT car.id,
                   car.data,
                   car.data_saida,
                   car.rota,
                   car.placa,
                   car.observacao,
                   car.observacao_extra,
                   car.observacao_cor,
                   car.revisado,
                   car.motorista_id,
                   car.ajudante_id,
                   mot.nome AS motorista_nome,
                   aj.nome AS ajudante_nome
            FROM carregamentos car
            LEFT JOIN colaboradores mot ON mot.id = car.motorista_id
            LEFT JOIN colaboradores aj ON aj.id = car.ajudante_id
            WHERE car.data = ?
            ORDER BY car.rota ASC, car.id ASC;
            """,
            (data_iso,),
        )
        return [dict(row) for row in cur.fetchall()]


def obter_carregamento(carregamento_id: int) -> dict | None:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT car.*, mot.nome AS motorista_nome, aj.nome AS ajudante_nome
            FROM carregamentos car
            LEFT JOIN colaboradores mot ON mot.id = car.motorista_id
            LEFT JOIN colaboradores aj ON aj.id = car.ajudante_id
            WHERE car.id = ?;
            """,
            (carregamento_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def duplicar_carregamento(carregamento_id: int) -> int:
    registro = obter_carregamento(carregamento_id)
    if not registro:
        raise ValueError("Carregamento não encontrado.")
    data_base = registro.get("data") or date.today().isoformat()
    rota_original = (registro.get("rota") or "").strip()
    nova_rota = rota_original
    numero_part = rota_original
    destino_part = ""
    if " - " in rota_original:
        numero_part, destino_part = rota_original.split(" - ", 1)
        numero_part = numero_part.strip()
        destino_part = destino_part.strip()
    match = re.match(r"^(\d+)(.*)$", numero_part)
    if match:
        base_num = int(match.group(1))
        sufixo = match.group(2) or ""
        contador = base_num + 1
        while True:
            nova_num = f"{contador}{sufixo}"
            nova_rota = f"{nova_num} - {destino_part}" if destino_part else nova_num
            if not carregamento_existe_para_rota(data_base, nova_rota):
                break
            contador += 1
    return salvar_carregamento(
        data_base,
        nova_rota or "",
        None,
        None,
        None,
        registro.get("observacao") or "0",
        registro.get("observacao_extra"),
        registro.get("observacao_cor"),
        registro.get("data_saida"),
        revisado=False,
    )


def obter_data_saida_registro(registro: dict) -> str:
    data_registro = (registro.get("data") or "").strip()
    base = parse_date(data_registro)
    valor = (registro.get("data_saida") or "").strip()
    if valor:
        saida_dt = parse_date(valor)
        if base and saida_dt and saida_dt < base:
            valor = ""
        elif saida_dt:
            return valor
    if not base:
        return date.today().isoformat()
    dias = 3 if base.weekday() == 4 else 1
    return (base + timedelta(days=dias)).isoformat()

# Oficinas


def salvar_oficina(
    data_iso: str,
    motorista_id: int | None,
    placa: str,
    observacao: str,
    observacao_extra: str | None = None,
    data_saida: str | None = None,
    observacao_cor: str | None = None,
) -> int:
    disponibilidade = verificar_disponibilidade(data_iso)
    indis_colaboradores = disponibilidade.get("motoristas", set()).union(
        disponibilidade.get("ajudantes", set())
    )
    if motorista_id and motorista_id in indis_colaboradores:
        raise ValueError("Motorista indisponível nesta data.")

    data_saida_iso = data_saida or calcular_data_saida_padrao(data_iso)
    with get_connection() as conn:
        cur = conn.cursor()
        novo_id = insert_and_get_id(
            cur,
            """
            INSERT INTO oficinas (
                data,
                motorista_id,
                placa,
                observacao,
                observacao_extra,
                data_saida,
                observacao_cor
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                data_iso,
                motorista_id,
                placa,
                observacao,
                (observacao_extra or "").strip() or None,
                data_saida_iso,
                observacao_cor.strip() if observacao_cor else None,
            ),
        )
        conn.commit()
        return novo_id


def listar_oficinas(data_iso: str) -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ofi.id,
                   ofi.data,
                   ofi.motorista_id,
                   ofi.placa,
                   ofi.observacao,
                   ofi.observacao_extra,
                   ofi.data_saida,
                   ofi.observacao_cor,
                   col.nome AS motorista_nome
            FROM oficinas ofi
            LEFT JOIN colaboradores col ON col.id = ofi.motorista_id
            WHERE ofi.data = ?
            ORDER BY ofi.id ASC;
            """,
            (data_iso,),
        )
        return [dict(row) for row in cur.fetchall()]


def listar_oficinas_por_data_saida(data_iso: str) -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ofi.id,
                   ofi.data,
                   ofi.motorista_id,
                   ofi.placa,
                   ofi.observacao,
                   ofi.observacao_extra,
                   ofi.data_saida,
                   ofi.observacao_cor,
                   col.nome AS motorista_nome
            FROM oficinas ofi
            LEFT JOIN colaboradores col ON col.id = ofi.motorista_id
            WHERE COALESCE(ofi.data_saida, ofi.data) = ?
            ORDER BY ofi.id ASC;
            """,
            (data_iso,),
        )
        return [dict(row) for row in cur.fetchall()]


def obter_oficina(oficina_id: int) -> dict | None:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ofi.*, col.nome AS motorista_nome
            FROM oficinas ofi
            LEFT JOIN colaboradores col ON col.id = ofi.motorista_id
            WHERE ofi.id = ?;
            """,
            (oficina_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def editar_oficina(
    oficina_id: int,
    motorista_id: int | None,
    placa: str,
    observacao: str,
    observacao_extra: str | None = None,
    data_saida: str | None = None,
    observacao_cor: str | None = None,
) -> None:
    data_saida_iso = data_saida or None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE oficinas
            SET motorista_id = ?, placa = ?, observacao = ?, observacao_extra = ?, data_saida = ?, observacao_cor = ?
            WHERE id = ?;
            """,
            (
                motorista_id,
                placa,
                observacao,
                (observacao_extra or "").strip() or None,
                data_saida_iso,
                observacao_cor.strip() if observacao_cor else None,
                oficina_id,
            ),
        )
        conn.commit()


def excluir_oficina(oficina_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM oficinas WHERE id = ?;", (oficina_id,))
        conn.commit()


# Rotas semanais


def listar_rotas_semanais(dia_semana: str) -> list[dict]:
    dia = normalizar_dia_semana(dia_semana)
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, dia_semana, rota, destino, observacao
            FROM rotas_semanais
            WHERE dia_semana = ?
            ORDER BY LOWER(rota) ASC;
            """,
            (dia,),
        )
        return [dict(row) for row in cur.fetchall()]


def adicionar_rota_semana(dia_semana: str, rota: str, destino: str, observacao: str) -> int:
    dia = normalizar_dia_semana(dia_semana)
    with get_connection() as conn:
        cur = conn.cursor()
        novo_id = insert_and_get_id(
            cur,
            """
            INSERT INTO rotas_semanais (dia_semana, rota, destino, observacao)
            VALUES (?, ?, ?, ?);
            """,
            (dia, rota.strip(), destino.strip(), observacao.strip()),
        )
        conn.commit()
        return novo_id


def editar_rota_semana(rota_id: int, dia_semana: str, rota: str, destino: str, observacao: str) -> None:
    dia = normalizar_dia_semana(dia_semana)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE rotas_semanais
            SET dia_semana = ?, rota = ?, destino = ?, observacao = ?
            WHERE id = ?;
            """,
            (dia, rota.strip(), destino.strip(), observacao.strip(), rota_id),
        )
        conn.commit()


def remover_rota_semana(rota_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM rotas_semanais WHERE id = ?;", (rota_id,))
        conn.commit()


def listar_rotas_para_data(data_iso: str) -> list[dict]:
    dia_semana = obter_dia_semana_por_data(data_iso)
    return listar_rotas_semanais(dia_semana)


def listar_rotas_semanais_pendentes(data_iso: str | None) -> list[dict]:
    data_base = _normalizar_data_iso(data_iso)
    if not data_base:
        return []
    rotas = listar_rotas_para_data(data_base)
    if not rotas:
        return []
    rotas_suprimidas = listar_rotas_suprimidas(data_base)
    pendentes: list[dict] = []
    for rota in rotas:
        texto_rota = (rota.get("rota") or "").strip()
        if not texto_rota:
            continue
        destino = (rota.get("destino") or "").strip()
        if destino:
            texto_rota = f"{texto_rota} - {destino}"
        if texto_rota in rotas_suprimidas:
            continue
        if carregamento_existe_para_rota(data_base, texto_rota):
            continue
        pendentes.append(
            {
                "rota": texto_rota,
                "destino": destino,
            }
        )
    return pendentes


def carregamento_existe_para_rota(data_iso: str, rota_texto: str) -> bool:
    if not data_iso or not rota_texto:
        return False
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM carregamentos WHERE data = ? AND rota = ? LIMIT 1;",
            (data_iso, rota_texto),
        )
        return cur.fetchone() is not None


def _normalizar_data_iso(valor: str | None) -> str | None:
    data = parse_date(valor or "")
    return data.isoformat() if data else None


def listar_rotas_suprimidas(data_iso: str | None) -> set[str]:
    data_base = _normalizar_data_iso(data_iso)
    if not data_base:
        return set()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT rota FROM rotas_suprimidas WHERE data = ?;", (data_base,))
        return {row[0] for row in cur.fetchall()}


def registrar_rota_suprimida(data_iso: str | None, rota_texto: str | None) -> None:
    data_base = _normalizar_data_iso(data_iso)
    rota = (rota_texto or "").strip()
    if not data_base or not rota:
        return
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO rotas_suprimidas (data, rota) VALUES (?, ?);",
            (data_base, rota),
        )
        conn.commit()


def limpar_rotas_suprimidas(data_iso: str | None) -> None:
    data_base = _normalizar_data_iso(data_iso)
    if not data_base:
        return
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM rotas_suprimidas WHERE data = ?;", (data_base,))
        conn.commit()


def preencher_carregamentos_automaticos(data_iso: str, data_saida_iso: str | None = None) -> int:
    data_base = _normalizar_data_iso(data_iso)
    if not data_base:
        return 0
    data_saida_iso = _normalizar_data_iso(data_saida_iso)
    rotas_suprimidas = listar_rotas_suprimidas(data_base)
    rotas = listar_rotas_para_data(data_base)
    if not rotas:
        return 0
    inseridos = 0
    for rota in rotas:
        texto_rota = (rota.get("rota") or "").strip()
        if not texto_rota:
            continue
        destino = (rota.get("destino") or "").strip()
        if destino:
            texto_rota = f"{texto_rota} - {destino}"
        if texto_rota in rotas_suprimidas:
            continue
        if carregamento_existe_para_rota(data_base, texto_rota):
            continue
        observacao_extra = (rota.get("observacao") or "").strip() or None
        try:
            salvar_carregamento(
                data_base,
                texto_rota,
                None,
                None,
                None,
                OBSERVACAO_OPCOES[0],
                observacao_extra=observacao_extra,
                data_saida=data_saida_iso,
                revisado=False,
            )
            inseridos += 1
        except DBError:
            continue
    return inseridos


def sincronizar_rota_semana_com_carregamentos(
    data_iso: str | None,
    dia_semana: str,
    rota_texto: str,
    destino: str,
    observacao: str,
    data_saida_iso: str | None = None,
) -> bool:
    data_base = _normalizar_data_iso(data_iso)
    if not data_base or not rota_texto:
        return False
    dia_chave = normalizar_dia_semana(dia_semana)
    if obter_dia_semana_por_data(data_base) != dia_chave:
        return False
    texto_rota = rota_texto.strip()
    destino = destino.strip()
    if destino:
        texto_rota = f"{texto_rota} - {destino}"
    if carregamento_existe_para_rota(data_base, texto_rota):
        return False
    data_saida_iso = _normalizar_data_iso(data_saida_iso)
    observacao_extra = observacao.strip() or None
    try:
        salvar_carregamento(
            data_base,
            texto_rota,
            None,
            None,
            None,
            OBSERVACAO_OPCOES[0],
            observacao_extra=observacao_extra,
            data_saida=data_saida_iso,
            revisado=False,
        )
    except DBError:
        return False
    return True


# Escala (CD)


def adicionar_escala_cd(data_iso: str, motorista_id: int | None, ajudante_id: int | None, observacao: str) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        novo_id = insert_and_get_id(
            cur,
            """
            INSERT INTO escala_cd (data, motorista_id, ajudante_id, observacao)
            VALUES (?, ?, ?, ?);
            """,
            (data_iso, motorista_id, ajudante_id, observacao.strip()),
        )
        conn.commit()
        return novo_id


def listar_escala_cd(data_iso: str) -> list[dict]:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT e.id,
                   e.data,
                   e.motorista_id,
                   e.ajudante_id,
                   e.observacao,
                   mot.nome AS motorista_nome,
                   aj.nome AS ajudante_nome
            FROM escala_cd e
            LEFT JOIN colaboradores mot ON mot.id = e.motorista_id
            LEFT JOIN colaboradores aj ON aj.id = e.ajudante_id
            WHERE e.data = ?
            ORDER BY e.id ASC;
            """,
            (data_iso,),
        )
        return [dict(row) for row in cur.fetchall()]


def obter_escala_cd(escala_id: int) -> dict | None:
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT e.*, mot.nome AS motorista_nome, aj.nome AS ajudante_nome
            FROM escala_cd e
            LEFT JOIN colaboradores mot ON mot.id = e.motorista_id
            LEFT JOIN colaboradores aj ON aj.id = e.ajudante_id
            WHERE e.id = ?;
            """,
            (escala_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def editar_escala_cd(escala_id: int, motorista_id: int | None, ajudante_id: int | None, observacao: str) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE escala_cd
            SET motorista_id = ?, ajudante_id = ?, observacao = ?
            WHERE id = ?;
            """,
            (motorista_id, ajudante_id, observacao.strip(), escala_id),
        )
        conn.commit()


def excluir_escala_cd(escala_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM escala_cd WHERE id = ?;", (escala_id,))
        conn.commit()

# Ajustes e log


def listar_ajustes_por_carregamentos(carregamento_ids: list[int]) -> dict[int, list[dict]]:
    if not carregamento_ids:
        return {}
    placeholders = ",".join(["?"] * len(carregamento_ids))
    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, carregamento_id, data_ajuste, duracao_anterior, duracao_nova, observacao_ajuste
            FROM ajustes_rotas
            WHERE carregamento_id IN ({placeholders})
            ORDER BY data_ajuste ASC, id ASC;
            """,
            carregamento_ids,
        )
        rows = [dict(row) for row in cur.fetchall()]
    agrupado: dict[int, list[dict]] = {}
    for row in rows:
        agrupado.setdefault(row["carregamento_id"], []).append(row)
    return agrupado


def registrar_ajuste_rota(
    carregamento_id: int,
    duracao_anterior: int,
    duracao_nova: int,
    observacao_ajuste: str | None = None,
) -> None:
    data_ajuste = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ajustes_rotas (
                carregamento_id,
                data_ajuste,
                duracao_anterior,
                duracao_nova,
                observacao_ajuste
            )
            VALUES (?, ?, ?, ?, ?);
            """,
            (
                carregamento_id,
                data_ajuste,
                duracao_anterior,
                duracao_nova,
                (observacao_ajuste or "").strip() or None,
            ),
        )
        conn.commit()


def atualizar_bloqueios_para_ajuste(
    carregamento_id: int,
    nova_data_fim_iso: str,
    liberar_imediato: bool = False,
) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        if liberar_imediato:
            cur.execute("DELETE FROM bloqueios WHERE carregamento_id = ?;", (carregamento_id,))
        else:
            cur.execute(
                "UPDATE bloqueios SET data_fim = ? WHERE carregamento_id = ?;",
                (nova_data_fim_iso, carregamento_id),
            )
        conn.commit()


def remover_ajustes_por_carregamento(carregamento_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ajustes_rotas WHERE carregamento_id = ?;", (carregamento_id,))
        conn.commit()


def montar_resumo_ajustes(duracao_planejada: int, ajustes: list[dict]) -> str:
    if not ajustes:
        return f"Planejado: {dias_para_texto(duracao_planejada)}"
    resumo = ""
    anterior = duracao_planejada
    for ajuste in ajustes:
        novo = ajuste.get("duracao_nova", anterior)
        if novo > anterior:
            diff = novo - anterior
            resumo = f"Era {dias_para_texto(anterior)}, ficou +{diff} = {dias_para_texto(novo)}"
        elif novo < anterior:
            resumo = f"Era {dias_para_texto(anterior)}, voltaram em {dias_para_texto(novo)}"
        else:
            resumo = f"Ajustado e mantido em {dias_para_texto(novo)}"
        anterior = novo
    return resumo


def consultar_log_carregamentos(filtros: dict) -> list[dict]:
    query = [
        """
        SELECT car.id,
               car.data,
               car.data_saida,
               car.rota,
               car.placa,
               car.observacao,
               car.observacao_extra,
               car.motorista_id,
               car.ajudante_id,
               mot.nome AS motorista_nome,
               aj.nome AS ajudante_nome
        FROM carregamentos car
        LEFT JOIN colaboradores mot ON mot.id = car.motorista_id
        LEFT JOIN colaboradores aj ON aj.id = car.ajudante_id
        WHERE 1 = 1
        """
    ]
    params: list = []
    if filtros.get("data_inicio"):
        query.append("AND car.data >= ?")
        params.append(filtros["data_inicio"])
    if filtros.get("data_fim"):
        query.append("AND car.data <= ?")
        params.append(filtros["data_fim"])
    if filtros.get("motorista_id"):
        query.append("AND car.motorista_id = ?")
        params.append(filtros["motorista_id"])
    if filtros.get("placa"):
        query.append("AND UPPER(car.placa) = ?")
        params.append(filtros["placa"].upper())
    query.append("ORDER BY car.data DESC, car.id DESC")

    with get_connection(dict_rows=True) as conn:
        cur = conn.cursor()
        cur.execute(" ".join(query), tuple(params))
        registros = [dict(row) for row in cur.fetchall()]

    ajustes_map = listar_ajustes_por_carregamentos([reg["id"] for reg in registros])
    hoje = date.today()
    resultado: list[dict] = []

    for registro in registros:
        observacao_padrao = (registro.get("observacao") or "0").strip()
        duracao_planejada = OBSERVACAO_DURACAO.get(observacao_padrao, 0)
        ajustes = ajustes_map.get(registro["id"], [])
        duracao_efetiva = ajustes[-1]["duracao_nova"] if ajustes else duracao_planejada
        data_inicio_iso = obter_data_saida_registro(registro)
        try:
            data_inicio_dt = datetime.strptime(data_inicio_iso, "%Y-%m-%d").date()
        except ValueError:
            data_inicio_dt = hoje
            data_inicio_iso = hoje.isoformat()
        data_fim_dt = data_inicio_dt + timedelta(days=duracao_efetiva)
        data_fim_iso = data_fim_dt.isoformat()

        finalizado_manual = bool(ajustes) and duracao_efetiva <= 0
        if finalizado_manual:
            status = "Finalizado"
        elif hoje < data_inicio_dt:
            status = "Em andamento"
        elif hoje < data_fim_dt:
            status = "Em andamento"
        else:
            status = "Finalizado"

        status_filtro = filtros.get("status")
        if status_filtro and status_filtro != "Todos":
            if status_filtro == "Em andamento" and status != "Em andamento":
                continue
            if status_filtro == "Finalizados" and status != "Finalizado":
                continue

        restante = max((data_fim_dt - hoje).days, 0)
        andamento_texto = ""
        if status == "Em andamento":
            if restante > 0:
                andamento_texto = f"{observacao_padrao or 'ROTA'} - faltando {restante}"
            else:
                andamento_texto = f"{observacao_padrao or 'ROTA'} - retorna hoje"

        ajudante_nome = formatar_ajudante_nome(
            registro.get("ajudante_nome") or DISPLAY_VAZIO,
            registro.get("ajudante_id"),
        )
        placa_valor = (registro.get("placa") or "").upper() or DISPLAY_VAZIO
        motorista_valor = registro.get("motorista_nome") or DISPLAY_VAZIO
        tem_dados = any(
            valor and valor != DISPLAY_VAZIO for valor in (placa_valor, motorista_valor, ajudante_nome)
        )
        resultado.append(
            {
                "id": registro["id"],
                "data": registro.get("data"),
                "data_br": data_iso_para_br(registro.get("data")),
                "data_saida": data_inicio_iso,
                "data_saida_br": data_iso_para_br(data_inicio_iso),
                "data_fim": data_fim_iso,
                "data_fim_br": data_iso_para_br(data_fim_iso),
                "rota": registro.get("rota") or DISPLAY_VAZIO,
                "placa": placa_valor,
                "motorista": motorista_valor,
                "ajudante": ajudante_nome,
                "motorista_id": registro.get("motorista_id"),
                "ajudante_id": registro.get("ajudante_id"),
                "observacao": observacao_padrao,
                "duracao_planejada": duracao_planejada,
                "duracao_efetiva": duracao_efetiva,
                "status": status,
                "status_texto": andamento_texto if status == "Em andamento" else "",
                "resumo": montar_resumo_ajustes(duracao_planejada, ajustes),
                "ajustes": ajustes,
                "log_vazio": not tem_dados,
            }
        )

    if filtros.get("status") == "Em andamento":
        resultado.sort(key=lambda item: item.get("log_vazio", False))

    return resultado

