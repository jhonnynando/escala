from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageColor, ImageDraw, ImageFont
from openpyxl import Workbook
from openpyxl.styles import Font

from .db import FONT_PATH, LOGO_PATH, REPORTS_DIR
from .services import (
    COR_AZUL,
    COR_AZUL_GRADIENTE_FIM,
    COR_TEXTO,
    COR_VERMELHA,
    DISPLAY_VAZIO,
    ajustar_cor_marcador,
    combinar_observacoes,
    data_iso_para_extenso,
    formatar_ajudante_nome,
)


def carregar_fonte(tamanho: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    # Use a single variable font with weight variation when available.
    try:
        fonte = ImageFont.truetype(str(FONT_PATH), tamanho)
        if bold:
            try:
                fonte.set_variation_by_name("Bold")
            except Exception:
                try:
                    axes = fonte.get_variation_axes()
                    if axes:
                        peso = axes[0].get("maximum", 700)
                        fonte.set_variation_by_axes([peso])
                except Exception:
                    pass
        return fonte
    except OSError:
        return ImageFont.load_default()


def criar_gradiente_horizontal(largura: int, altura: int, cor_inicio: str, cor_fim: str) -> Image.Image:
    img = Image.new("RGB", (largura, altura), cor_inicio)
    r1, g1, b1 = ImageColor.getrgb(cor_inicio)
    r2, g2, b2 = ImageColor.getrgb(cor_fim)
    draw = ImageDraw.Draw(img)
    for x in range(largura):
        ratio = x / max(largura - 1, 1)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        draw.line([(x, 0), (x, altura)], fill=(r, g, b))
    return img


def medir_texto(draw: ImageDraw.ImageDraw, texto: str, fonte: ImageFont.ImageFont):
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), texto, font=fonte)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    if hasattr(draw, "textsize"):
        return draw.textsize(texto, font=fonte)
    if hasattr(fonte, "getbbox"):
        bbox = fonte.getbbox(texto)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    largura = len(texto) * fonte.size * 0.6
    return largura, fonte.size


def desenhar_texto_cabecalho(
    draw: ImageDraw.ImageDraw,
    texto: str,
    x: float,
    y: float,
    largura_coluna: float,
    altura: float,
    fonte: ImageFont.ImageFont,
    cor: str,
    alinhado_centro: bool = False,
    padding: int = 12,
):
    texto_header = texto.upper()
    if texto_header in {"Nº", "N°"}:
        fonte_peq = carregar_fonte(max(10, int(fonte.size * 0.65)), bold=True)
        w_n, h_n = medir_texto(draw, "N", fonte)
        w_o, h_o = medir_texto(draw, "o", fonte_peq)
        total_w = w_n + w_o
        if alinhado_centro:
            texto_x = x + (largura_coluna - total_w) / 2
        else:
            texto_x = x + padding
        texto_y = y + (altura - h_n) / 2
        draw.text((texto_x, texto_y), "N", fill=cor, font=fonte)
        draw.text((texto_x + w_n - 2, texto_y - h_o * 0.35), "o", fill=cor, font=fonte_peq)
        return

    texto_w, texto_h = medir_texto(draw, texto_header, fonte)
    if alinhado_centro:
        texto_x = x + (largura_coluna - texto_w) / 2
    else:
        texto_x = x + padding
    texto_y = y + (altura - texto_h) / 2
    draw.text((texto_x, texto_y), texto_header, fill=cor, font=fonte)


def exportar_log_para_excel(registros: list[dict]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "LOG"
    cabecalho = [
        "Data Carregamento",
        "Data Saída",
        "Motorista",
        "Ajudante",
        "Placa",
        "Rota",
        "Duração planejada (dias)",
        "Duração efetiva (dias)",
        "Status",
        "Resumo histórico",
    ]
    ws.append(cabecalho)
    if Font:
        for cell in ws[1]:
            cell.font = Font(bold=True)
    for item in registros:
        ws.append(
            [
                item.get("data_br"),
                item.get("data_saida_br"),
                item.get("motorista"),
                item.get("ajudante"),
                item.get("placa"),
                item.get("rota"),
                item.get("duracao_planejada"),
                item.get("duracao_efetiva"),
                item.get("status"),
                item.get("resumo"),
            ]
        )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"log_escala_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    caminho = REPORTS_DIR / nome_arquivo
    wb.save(caminho)
    return caminho


def exportar_relatorio_imagem(
    aba_nome: str,
    titulo: str,
    colunas: list[str],
    linhas: list[list[str]],
    data_referencia: str,
    subtitulos: list[str] | None = None,
    col_widths: list[float] | None = None,
    highlight_col: int | None = None,
    highlight_colors: list[str | None] | None = None,
) -> Path:
    if not linhas:
        linhas = [[DISPLAY_VAZIO for _ in colunas]]

    largura = 1920
    altura = 1080
    header_altura = 60
    rodape_altura = 30
    margem = 35
    tabela_top = header_altura + 15
    tabela_bottom = altura - rodape_altura - 15
    largura_util = largura - 2 * margem

    if not col_widths:
        col_widths = [1 / len(colunas)] * len(colunas)

    imagem = Image.new("RGB", (largura, altura), "#E4EBF7")
    draw = ImageDraw.Draw(imagem)

    font_logo = carregar_fonte(24, bold=True)
    font_header = carregar_fonte(16, bold=True)
    font_sub = carregar_fonte(12, bold=True)
    font_table_header = carregar_fonte(12, bold=True)
    font_table = carregar_fonte(10, bold=True)

    draw.rectangle([0, 0, largura, header_altura], fill=COR_AZUL)
    draw.rectangle([0, 0, 360, header_altura], fill=COR_VERMELHA)
    if LOGO_PATH.exists():
        try:
            with Image.open(LOGO_PATH) as logo_img:
                logo_rel = logo_img.convert("RGBA").resize((35, 35))
            imagem.paste(logo_rel, (25, 15), logo_rel)
        except OSError:
            draw.text((50, 30), "JR", fill="white", font=font_logo)
    else:
        draw.text((50, 30), "JR", fill="white", font=font_logo)
    draw.text((100, 15), titulo.upper(), fill="white", font=font_header)
    draw.text(
        (100, 30),
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y')}",
        fill="white",
        font=font_sub,
    )
    draw.text(
        (100, 41),
        f"Base: {datetime.strptime(data_referencia, '%Y-%m-%d').strftime('%d/%m/%Y')}",
        fill="white",
        font=font_sub,
    )
    if subtitulos:
        offset = 41
        for linha in subtitulos:
            draw.text((1000, offset), linha, fill="white", font=font_sub)
            offset += 15

    def quebrar_texto(texto: str, largura_max: float):
        if not texto:
            return [DISPLAY_VAZIO]
        palavras = texto.split()
        linhas_q = []
        atual = ""
        for palavra in palavras:
            tentativa = (atual + " " + palavra).strip()
            largura_t, _ = medir_texto(draw, tentativa, font_table)
            if largura_t <= largura_max - 20:
                atual = tentativa
            else:
                if atual:
                    linhas_q.append(atual)
                atual = palavra
        if atual:
            linhas_q.append(atual)
        return linhas_q or [DISPLAY_VAZIO]

    y = tabela_top
    header_altura_linha = 40
    x = margem
    for idx, coluna in enumerate(colunas):
        largura_coluna = int(col_widths[idx] * largura_util)
        draw.rectangle([x, y, x + largura_coluna, y + header_altura_linha], fill="#1A3E78")
        desenhar_texto_cabecalho(
            draw,
            coluna,
            x,
            y,
            largura_coluna,
            header_altura_linha,
            font_table_header,
            "white",
            alinhado_centro=False,
            padding=10,
        )
        x += largura_coluna
    y += header_altura_linha

    linha_cor_1 = "#FFFFFF"
    linha_cor_2 = "#F5F6FA"
    linha_altura_base = 44

    for linha_idx, linha in enumerate(linhas):
        x = margem
        altura_linha = linha_altura_base
        celulas_processadas = []
        for col_idx, valor in enumerate(linha):
            largura_coluna = int(col_widths[col_idx] * largura_util)
            linhas_texto = quebrar_texto(str(valor), largura_coluna)
            altura_linha = max(altura_linha, 24 * len(linhas_texto) + 16)
            celulas_processadas.append((largura_coluna, linhas_texto))

        if y + altura_linha > tabela_bottom:
            break

        fundo = linha_cor_1 if linha_idx % 2 == 0 else linha_cor_2

        for col_idx, (largura_coluna, linhas_texto) in enumerate(celulas_processadas):
            bg = fundo
            if highlight_col is not None and col_idx == highlight_col:
                cor_personalizada = None
                if highlight_colors and linha_idx < len(highlight_colors):
                    cor_personalizada = ajustar_cor_marcador(highlight_colors[linha_idx])
                if cor_personalizada:
                    bg = cor_personalizada
                elif (linhas_texto[0] or "").strip().upper() not in ("0", DISPLAY_VAZIO):
                    bg = "#FFF2B2"
            draw.rectangle([x, y, x + largura_coluna, y + altura_linha], fill=bg, outline="#C1C7D6")
            text_y = y + 8
            for linha_texto in linhas_texto:
                draw.text((x + 10, text_y), linha_texto, fill=COR_TEXTO, font=font_table)
                text_y += 24
            x += largura_coluna
        y += altura_linha

    draw.text(
        (margem, altura - rodape_altura),
        "JR Ferragens e Madeiras | Sistema JR Escala",
        fill=COR_TEXTO,
        font=font_sub,
    )

    nome_arquivo = f"relatorio_JR_{aba_nome}_{data_referencia}.png"
    caminho = REPORTS_DIR / nome_arquivo
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    imagem.save(caminho)
    return caminho


def gerar_relatorio_moderno(
    arquivo_stub: str,
    titulo_header: str,
    linha_principal_rotulo: str,
    data_principal_iso: str | None,
    linha_secundaria_rotulo: str | None,
    data_secundaria_iso: str | None,
    total_legenda: str,
    colunas: list[str],
    col_widths: list[float],
    linhas: list[list[str]],
    col_align_center: set[int] | None = None,
    highlight_col: int | None = None,
    highlight_colors: list[str | None] | None = None,
    arquivo_data_iso: str | None = None,
    fallback_highlight: bool = True,
) -> Path:
    if not linhas:
        linhas = [[DISPLAY_VAZIO for _ in colunas]]

    col_align_center = col_align_center or set()
    highlight_colors = highlight_colors or []

    largura = 1920
    header_altura = 140
    rodape_altura = 40
    margem = 40
    table_header_altura = 48
    linha_altura_base = 48
    table_width = largura - 2 * margem
    col_px = [int(table_width * proporcao) for proporcao in col_widths]

    font_titulo = carregar_fonte(29, bold=True)
    font_info = carregar_fonte(21, bold=True)
    font_info_secundario = carregar_fonte(19, bold=True)
    font_header_table = carregar_fonte(18, bold=True)
    font_table = carregar_fonte(16, bold=True)
    font_footer = carregar_fonte(13, bold=True)
    line_height = getattr(font_table, "size", 13) + 6

    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def quebrar_texto(texto: str | None, largura_coluna: int) -> list[str]:
        if texto is None:
            conteudo = DISPLAY_VAZIO
        else:
            conteudo = str(texto)
        conteudo = conteudo.strip()
        if conteudo == "":
            return [""]
        palavras = conteudo.split()
        linhas_resultado: list[str] = []
        atual = ""
        while palavras:
            palavra = palavras.pop(0)
            tentativa = (atual + " " + palavra).strip()
            largura_t, _ = medir_texto(dummy_draw, tentativa, font_table)
            if largura_t <= largura_coluna - 24:
                atual = tentativa
            else:
                if atual:
                    linhas_resultado.append(atual)
                atual = palavra
        if atual:
            linhas_resultado.append(atual)
        return linhas_resultado or [DISPLAY_VAZIO]

    linhas_processadas: list[tuple[int, list[list[str]], str | None]] = []
    total_altura_tabela = table_header_altura
    for idx_linha, linha in enumerate(linhas):
        celulas = []
        altura_linha = linha_altura_base
        for col_idx in range(len(colunas)):
            valor = linha[col_idx] if col_idx < len(linha) else ""
            largura_coluna = col_px[col_idx]
            linhas_texto = quebrar_texto(str(valor) if valor is not None else DISPLAY_VAZIO, largura_coluna)
            altura_linha = max(altura_linha, len(linhas_texto) * line_height + 16)
            celulas.append(linhas_texto)
        cor_marcador = highlight_colors[idx_linha] if idx_linha < len(highlight_colors) else None
        linhas_processadas.append((altura_linha, celulas, cor_marcador))
        total_altura_tabela += altura_linha

    altura_minima = 1080
    altura_calculada = header_altura + 25 + total_altura_tabela + rodape_altura + 25
    altura = max(altura_minima, int(altura_calculada))
    tabela_top = header_altura + 25

    imagem = Image.new("RGB", (largura, altura), "#F1F3F6")
    draw = ImageDraw.Draw(imagem)
    grad = criar_gradiente_horizontal(largura, header_altura, COR_AZUL, COR_AZUL_GRADIENTE_FIM)
    imagem.paste(grad, (0, 0))

    logo_pos = (margem, 35)
    if LOGO_PATH.exists():
        try:
            with Image.open(LOGO_PATH) as logo_img:
                logo_rel = logo_img.convert("RGBA").resize((80, 80))
            imagem.paste(logo_rel, logo_pos, logo_rel)
        except OSError:
            draw.text((logo_pos[0], logo_pos[1] + 20), "JR", fill="#FFFFFF", font=font_titulo)
    else:
        draw.text((logo_pos[0], logo_pos[1] + 20), "JR", fill="#FFFFFF", font=font_titulo)

    titulo_x = logo_pos[0] + 110
    draw.text((titulo_x, 32), titulo_header, fill="#FFFFFF", font=font_titulo)

    label_principal = (linha_principal_rotulo or "Informação").strip().upper()
    texto_principal = f"{label_principal}: {data_iso_para_extenso(data_principal_iso)}"
    draw.text((titulo_x, 70), texto_principal, fill="#FFFFFF", font=font_info)

    if linha_secundaria_rotulo:
        label_secundario = linha_secundaria_rotulo.strip().upper()
        texto_secundario = f"{label_secundario}: {data_iso_para_extenso(data_secundaria_iso or data_principal_iso)}"
        draw.text((titulo_x, 98), texto_secundario, fill="#FFFFFF", font=font_info)

    if total_legenda:
        texto_total = total_legenda
        texto_total_w, _ = medir_texto(draw, texto_total, font_info_secundario)
        draw.text(
            (largura - margem - texto_total_w, header_altura - 30),
            texto_total,
            fill="#E8EEF8",
            font=font_info_secundario,
        )

    y = tabela_top
    x = margem
    header_bg = "#0A375F"
    for idx, coluna in enumerate(colunas):
        largura_coluna = col_px[idx]
        draw.rectangle([x, y, x + largura_coluna, y + table_header_altura], fill=header_bg)
        desenhar_texto_cabecalho(
            draw,
            coluna,
            x,
            y,
            largura_coluna,
            table_header_altura,
            font_header_table,
            "#FFFFFF",
            alinhado_centro=idx in col_align_center,
            padding=12,
        )
        x += largura_coluna
    y += table_header_altura

    linha_bg_1 = "#D9E7FB"
    linha_bg_2 = "#CFE0F7"
    borda_cor = "#6B84A6"
    borda_largura = 2

    for idx_linha, (altura_linha, celulas_processadas, cor_marcador_raw) in enumerate(linhas_processadas):
        x = margem
        bg = linha_bg_1 if idx_linha % 2 == 0 else linha_bg_2
        cor_marcador = ajustar_cor_marcador(cor_marcador_raw)
        for col_idx, linhas_texto in enumerate(celulas_processadas):
            largura_coluna = col_px[col_idx]
            cel_bg = bg
            if highlight_col is not None and col_idx == highlight_col:
                if cor_marcador:
                    cel_bg = cor_marcador
                elif fallback_highlight:
                    primeira_linha = (linhas_texto[0] or "").strip()
                    if primeira_linha and primeira_linha not in ("0", DISPLAY_VAZIO):
                        cel_bg = "#FFF2B2"
            draw.rectangle([x, y, x + largura_coluna, y + altura_linha], fill=cel_bg)
            for offset in range(borda_largura):
                draw.rectangle(
                    [
                        x + offset,
                        y + offset,
                        x + largura_coluna - offset,
                        y + altura_linha - offset,
                    ],
                    outline=borda_cor,
                )
            text_y = y + 8
            for linha_texto in linhas_texto:
                texto = linha_texto
                texto_w, _ = medir_texto(draw, texto, font_table)
                if col_idx in col_align_center:
                    texto_x = x + (largura_coluna - texto_w) / 2
                else:
                    texto_x = x + 12
                draw.text((texto_x, text_y), texto, fill=COR_TEXTO, font=font_table)
                text_y += line_height
            x += largura_coluna
        y += altura_linha

    draw.text(
        (margem, altura - rodape_altura + 6),
        "JR Ferragens e Madeiras | Sistema JR Escala",
        fill=COR_TEXTO,
        font=font_footer,
    )

    arquivo_base = arquivo_data_iso or data_principal_iso or date.today().isoformat()
    nome_arquivo = f"relatorio_JR_{arquivo_stub}_{arquivo_base}.png"
    caminho = REPORTS_DIR / nome_arquivo
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    imagem.save(caminho)
    return caminho


def _linha_relatorio_carregamento(item: dict) -> tuple[list[str], str | None]:
    rota_bruta = item.get("rota") or DISPLAY_VAZIO
    numero = DISPLAY_VAZIO
    destino = rota_bruta
    if " - " in rota_bruta:
        numero_part, destino_part = rota_bruta.split(" - ", 1)
        numero = numero_part.strip() or DISPLAY_VAZIO
        destino = destino_part.strip() or DISPLAY_VAZIO
    placa_texto = item.get("placa")
    placa_formatada = placa_texto.upper() if placa_texto else DISPLAY_VAZIO
    ajudante_nome = formatar_ajudante_nome(
        item.get("ajudante_nome") or DISPLAY_VAZIO,
        item.get("ajudante_id"),
        item.get("ajudante_funcao"),
    )
    obs_padrao = (item.get("observacao") or "").strip()
    obs_extra = (item.get("observacao_extra") or "").strip()
    if obs_padrao.lower() in ("none", "null"):
        obs_padrao = ""
    if obs_extra.lower() in ("none", "null"):
        obs_extra = ""
    if obs_padrao == "0":
        obs_padrao = ""
    if obs_padrao and obs_extra:
        observacao_relatorio = f"{obs_padrao} - {obs_extra}"
    elif obs_padrao:
        observacao_relatorio = obs_padrao
    elif obs_extra:
        observacao_relatorio = obs_extra
    else:
        observacao_relatorio = ""
    valores = [
        numero,
        placa_formatada,
        destino,
        item.get("motorista_nome") or DISPLAY_VAZIO,
        ajudante_nome,
        observacao_relatorio,
    ]
    return valores, (item.get("observacao_cor") or "").strip() or None


def desenhar_relatorio_carregamentos(
    data_carreg_iso: str,
    data_saida_iso: str,
    linhas: list[list[str]],
    total_registros: int,
    cores_obs: list[str | None] | None = None,
) -> Path:
    colunas = ["Nº", "Placa", "Rota", "Motorista", "Ajudante", "Obs."]
    col_widths = [0.08, 0.12, 0.25, 0.2, 0.2, 0.15]
    return gerar_relatorio_moderno(
        arquivo_stub="carregamentos",
        titulo_header="JR Escala - Carregamentos",
        linha_principal_rotulo="Carregamento",
        data_principal_iso=data_carreg_iso,
        linha_secundaria_rotulo="Rotas",
        data_secundaria_iso=data_saida_iso,
        total_legenda=f"Total de rotas: {total_registros}",
        colunas=colunas,
        col_widths=col_widths,
        linhas=linhas,
        col_align_center={0, 1},
        highlight_col=len(colunas) - 1,
        highlight_colors=cores_obs or [],
        arquivo_data_iso=data_carreg_iso,
        fallback_highlight=False,
    )


def gerar_relatorio_oficinas(data_iso: str, data_saida_iso: str, registros: list[dict]) -> Path:
    linhas: list[list[str]] = []
    cores: list[str | None] = []
    for item in registros:
        linhas.append(
            [
                item.get("motorista_nome") or DISPLAY_VAZIO,
                (item["placa"].upper() if item.get("placa") else DISPLAY_VAZIO),
                combinar_observacoes(item.get("observacao"), item.get("observacao_extra")),
            ]
        )
        cores.append(item.get("observacao_cor"))

    return gerar_relatorio_moderno(
        arquivo_stub="oficinas",
        titulo_header="JR Escala - Oficinas",
        linha_principal_rotulo="Oficina",
        data_principal_iso=data_iso,
        linha_secundaria_rotulo="Saída",
        data_secundaria_iso=data_saida_iso,
        total_legenda=f"Total de oficinas: {len(registros)}",
        colunas=["Motorista", "Placa", "Observações"],
        col_widths=[0.35, 0.2, 0.45],
        linhas=linhas,
        col_align_center={1},
        highlight_col=2,
        highlight_colors=cores,
        arquivo_data_iso=data_iso,
        fallback_highlight=False,
    )


def gerar_relatorio_escala_cd(data_iso: str, data_saida_iso: str, registros: list[dict]) -> Path:
    linhas = [
        [
            item.get("motorista_nome") or DISPLAY_VAZIO,
            item.get("ajudante_nome") or DISPLAY_VAZIO,
            item.get("observacao") or DISPLAY_VAZIO,
        ]
        for item in registros
    ]
    return gerar_relatorio_moderno(
        arquivo_stub="escala_cd",
        titulo_header="JR Escala - Escala (CD)",
        linha_principal_rotulo="Escala (CD)",
        data_principal_iso=data_iso,
        linha_secundaria_rotulo="Saída",
        data_secundaria_iso=data_saida_iso or data_iso,
        total_legenda=f"Total de equipes: {len(registros)}",
        colunas=["Motorista", "Ajudante", "Observações"],
        col_widths=[0.4, 0.3, 0.3],
        linhas=linhas,
        highlight_col=None,
        arquivo_data_iso=data_iso,
    )


def gerar_relatorio_folgas(data_iso: str, data_saida_iso: str | None, registros: list[dict]) -> Path:
    motoristas: list[str] = []
    ajudantes: list[str] = []
    for registro in registros:
        nome = (registro.get("nome") or "").strip()
        if not nome:
            continue
        funcao = (registro.get("funcao") or "").strip().lower()
        if funcao.startswith("motor"):
            motoristas.append(nome)
        elif funcao.startswith("ajud"):
            ajudantes.append(nome)
        else:
            motoristas.append(nome)
    motoristas.sort()
    ajudantes.sort()
    linhas: list[list[str]] = []
    max_len = max(len(motoristas), len(ajudantes))
    for idx in range(max_len):
        linhas.append([
            motoristas[idx] if idx < len(motoristas) else "",
            ajudantes[idx] if idx < len(ajudantes) else "",
        ])
    header_iso = data_saida_iso or data_iso
    return gerar_relatorio_moderno(
        arquivo_stub="folgas",
        titulo_header="FOLGA:",
        linha_principal_rotulo="Data",
        data_principal_iso=header_iso,
        linha_secundaria_rotulo=None,
        data_secundaria_iso=None,
        total_legenda=f"Total de folgas: {len(registros)}",
        colunas=["Motorista", "Ajudante"],
        col_widths=[0.5, 0.5],
        linhas=linhas,
        col_align_center=set(),
        highlight_col=None,
        highlight_colors=[],
        arquivo_data_iso=data_iso,
        fallback_highlight=False,
    )

