from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except Exception:  # psycopg2 pode nao estar instalado localmente
    psycopg2 = None

try:
    import psycopg
    from psycopg import rows as pg_rows
except Exception:  # psycopg (v3) pode nao estar instalado localmente
    psycopg = None
    pg_rows = None

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = Path(os.environ.get("JR_ESCALA_DB_PATH", BASE_DIR / "jr_escala_web.db"))
UPLOAD_DIR = Path(os.environ.get("JR_ESCALA_UPLOAD_DIR", BASE_DIR / "uploads"))
REPORTS_DIR = Path(os.environ.get("JR_ESCALA_REPORTS_DIR", BASE_DIR / "reports"))
LOGO_PATH = Path(os.environ.get("JR_ESCALA_LOGO_PATH", BASE_DIR / "static" / "img" / "logo-jr.png"))
FONT_PATH = Path(os.environ.get("JR_ESCALA_FONT_PATH", BASE_DIR / "static" / "fonts" / "Sora.ttf"))

def _clean_database_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value or None


DATABASE_URL = _clean_database_url(
    os.environ.get("JR_ESCALA_DATABASE_URL")
    or os.environ.get("NEON_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
)
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES and psycopg2:
    DBError = psycopg2.Error
elif USE_POSTGRES and psycopg:
    DBError = psycopg.Error
else:
    DBError = sqlite3.Error


def ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _translate_query(query: str) -> str:
    if not USE_POSTGRES:
        return query
    texto = query
    if re.search(r"\bINSERT\s+OR\s+IGNORE\b", texto, flags=re.IGNORECASE):
        texto = re.sub(r"\bINSERT\s+OR\s+IGNORE\b", "INSERT", texto, flags=re.IGNORECASE)
        texto = texto.rstrip().rstrip(";")
        texto = f"{texto} ON CONFLICT DO NOTHING;"
    texto = re.sub(r"COLLATE\s+NOCASE", "", texto, flags=re.IGNORECASE)
    texto = texto.replace("?", "%s")
    return texto


if psycopg2:
    class QmarkCursor(psycopg2.extensions.cursor):
        def execute(self, query, vars=None):
            return super().execute(_translate_query(query), vars)

        def executemany(self, query, vars_list):
            return super().executemany(_translate_query(query), vars_list)


    class QmarkDictCursor(psycopg2.extras.RealDictCursor):
        def execute(self, query, vars=None):
            return super().execute(_translate_query(query), vars)

        def executemany(self, query, vars_list):
            return super().executemany(_translate_query(query), vars_list)


class _PsycopgCursorWrapper:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, query, vars=None):
        return self._cur.execute(_translate_query(query), vars)

    def executemany(self, query, vars_list):
        return self._cur.executemany(_translate_query(query), vars_list)

    def __iter__(self):
        return iter(self._cur)

    def __getattr__(self, name):
        return getattr(self._cur, name)


class _PsycopgConnWrapper:
    def __init__(self, conn, dict_rows: bool):
        self._conn = conn
        self._dict_rows = dict_rows

    def cursor(self):
        if self._dict_rows and pg_rows:
            cur = self._conn.cursor(row_factory=pg_rows.dict_row)
        else:
            cur = self._conn.cursor()
        return _PsycopgCursorWrapper(cur)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._conn.__exit__(exc_type, exc, tb)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _postgres_connect(dict_rows: bool):
    sslmode = os.environ.get("JR_ESCALA_DB_SSLMODE", "require")
    try:
        connect_timeout = max(1, int(os.environ.get("JR_ESCALA_DB_CONNECT_TIMEOUT", "10")))
    except ValueError:
        connect_timeout = 10

    if psycopg2 is not None:
        cursor_factory = QmarkDictCursor if dict_rows else QmarkCursor
        return psycopg2.connect(
            DATABASE_URL,
            sslmode=sslmode,
            connect_timeout=connect_timeout,
            cursor_factory=cursor_factory,
        )
    if psycopg is not None:
        conn = psycopg.connect(
            DATABASE_URL,
            sslmode=sslmode,
            connect_timeout=connect_timeout,
        )
        return _PsycopgConnWrapper(conn, dict_rows)
    raise RuntimeError("Driver PostgreSQL nao instalado (psycopg2/psycopg).")


def _is_transient_connection_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        fragment in message
        for fragment in (
            "connection refused",
            "connection reset",
            "could not connect",
            "network is unreachable",
            "server closed the connection",
            "temporarily unavailable",
            "timeout expired",
            "timed out",
        )
    )


def get_connection(dict_rows: bool = False):
    ensure_dirs()
    if USE_POSTGRES:
        try:
            attempts = max(1, min(5, int(os.environ.get("JR_ESCALA_DB_CONNECT_ATTEMPTS", "3"))))
        except ValueError:
            attempts = 3

        for attempt in range(attempts):
            try:
                return _postgres_connect(dict_rows)
            except DBError as exc:
                if attempt == attempts - 1 or not _is_transient_connection_error(exc):
                    raise
                time.sleep(0.5 * (attempt + 1))

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    if dict_rows:
        conn.row_factory = sqlite3.Row
    return conn


def insert_and_get_id(cur, query: str, params: tuple) -> int | None:
    if USE_POSTGRES:
        texto = _translate_query(query).rstrip().rstrip(";")
        if "RETURNING" not in texto.upper():
            texto = f"{texto} RETURNING id"
        cur.execute(texto, params)
        row = cur.fetchone()
        if isinstance(row, dict):
            return row.get("id")
        return row[0] if row else None
    cur.execute(query, params)
    return cur.lastrowid


def init_db() -> None:
    ensure_dirs()
    if USE_POSTGRES:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS colaboradores (
                    id SERIAL PRIMARY KEY,
                    nome TEXT NOT NULL,
                    funcao TEXT NOT NULL,
                    observacao TEXT DEFAULT '',
                    foto TEXT DEFAULT '',
                    ativo INTEGER NOT NULL DEFAULT 1
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS folgas (
                    id SERIAL PRIMARY KEY,
                    data TEXT NOT NULL,
                    data_fim TEXT,
                    data_saida TEXT,
                    colaborador_id INTEGER NOT NULL REFERENCES colaboradores(id),
                    observacao_padrao TEXT,
                    observacao_extra TEXT,
                    observacao_cor TEXT,
                    UNIQUE(data, colaborador_id)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ferias (
                    id SERIAL PRIMARY KEY,
                    colaborador_id INTEGER NOT NULL REFERENCES colaboradores(id),
                    data_inicio TEXT NOT NULL,
                    data_fim TEXT NOT NULL,
                    observacao TEXT
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS carregamentos (
                    id SERIAL PRIMARY KEY,
                    data TEXT NOT NULL,
                    data_saida TEXT,
                    rota TEXT NOT NULL,
                    placa TEXT,
                    motorista_id INTEGER REFERENCES colaboradores(id),
                    ajudante_id INTEGER REFERENCES colaboradores(id),
                    observacao TEXT,
                    observacao_extra TEXT,
                    observacao_cor TEXT,
                    revisado INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(data, rota, placa)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oficinas (
                    id SERIAL PRIMARY KEY,
                    data TEXT NOT NULL,
                    motorista_id INTEGER REFERENCES colaboradores(id),
                    placa TEXT NOT NULL,
                    observacao TEXT,
                    observacao_extra TEXT,
                    data_saida TEXT,
                    observacao_cor TEXT,
                    UNIQUE(data, placa)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS caminhoes (
                    id SERIAL PRIMARY KEY,
                    placa TEXT UNIQUE NOT NULL,
                    modelo TEXT,
                    observacao TEXT,
                    ativo INTEGER NOT NULL DEFAULT 1
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bloqueios (
                    id SERIAL PRIMARY KEY,
                    colaborador_id INTEGER NOT NULL REFERENCES colaboradores(id),
                    data_inicio TEXT NOT NULL,
                    data_fim TEXT NOT NULL,
                    motivo TEXT,
                    carregamento_id INTEGER
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rotas_semanais (
                    id SERIAL PRIMARY KEY,
                    dia_semana TEXT NOT NULL,
                    rota TEXT NOT NULL,
                    destino TEXT,
                    observacao TEXT
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rotas_suprimidas (
                    id SERIAL PRIMARY KEY,
                    data TEXT NOT NULL,
                    rota TEXT NOT NULL,
                    UNIQUE(data, rota)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS escala_cd (
                    id SERIAL PRIMARY KEY,
                    data TEXT NOT NULL,
                    motorista_id INTEGER REFERENCES colaboradores(id),
                    ajudante_id INTEGER REFERENCES colaboradores(id),
                    observacao TEXT
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ajustes_rotas (
                    id SERIAL PRIMARY KEY,
                    carregamento_id INTEGER NOT NULL REFERENCES carregamentos(id),
                    data_ajuste TEXT NOT NULL,
                    duracao_anterior INTEGER NOT NULL,
                    duracao_nova INTEGER NOT NULL,
                    observacao_ajuste TEXT
                );
                """
            )
            cur.execute(
                "ALTER TABLE carregamentos ADD COLUMN IF NOT EXISTS revisado INTEGER NOT NULL DEFAULT 0;"
            )
            cur.execute("ALTER TABLE folgas ADD COLUMN IF NOT EXISTS data_saida TEXT;")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_colaboradores_funcao_ativo ON colaboradores (funcao, ativo);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_carregamentos_data ON carregamentos (data);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_carregamentos_data_rota ON carregamentos (data, rota);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_carregamentos_data_saida ON carregamentos (data_saida);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_folgas_data ON folgas (data);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_folgas_data_saida ON folgas (data_saida);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ferias_periodo ON ferias (data_inicio, data_fim);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_oficinas_data ON oficinas (data);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_oficinas_data_saida ON oficinas (data_saida);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_escala_cd_data ON escala_cd (data);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bloqueios_periodo ON bloqueios (data_inicio, data_fim);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bloqueios_carregamento ON bloqueios (carregamento_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rotas_semanais_dia ON rotas_semanais (dia_semana);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rotas_suprimidas_data ON rotas_suprimidas (data);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ajustes_rotas_carregamento ON ajustes_rotas (carregamento_id, id);")
            conn.commit()
        return

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS colaboradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                funcao TEXT NOT NULL,
                observacao TEXT DEFAULT '',
                foto TEXT DEFAULT '',
                ativo INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS folgas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                data_fim TEXT,
                data_saida TEXT,
                colaborador_id INTEGER NOT NULL,
                observacao_padrao TEXT,
                observacao_extra TEXT,
                observacao_cor TEXT,
                FOREIGN KEY(colaborador_id) REFERENCES colaboradores(id),
                UNIQUE(data, colaborador_id)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ferias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                colaborador_id INTEGER NOT NULL,
                data_inicio TEXT NOT NULL,
                data_fim TEXT NOT NULL,
                observacao TEXT,
                FOREIGN KEY(colaborador_id) REFERENCES colaboradores(id)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS carregamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                data_saida TEXT,
                rota TEXT NOT NULL,
                placa TEXT,
                motorista_id INTEGER,
                ajudante_id INTEGER,
                observacao TEXT,
                observacao_extra TEXT,
                observacao_cor TEXT,
                revisado INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(motorista_id) REFERENCES colaboradores(id),
                FOREIGN KEY(ajudante_id) REFERENCES colaboradores(id),
                UNIQUE(data, rota, placa)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS oficinas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                motorista_id INTEGER,
                placa TEXT NOT NULL,
                observacao TEXT,
                observacao_extra TEXT,
                data_saida TEXT,
                observacao_cor TEXT,
                FOREIGN KEY(motorista_id) REFERENCES colaboradores(id),
                UNIQUE(data, placa)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS caminhoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                placa TEXT UNIQUE NOT NULL,
                modelo TEXT,
                observacao TEXT,
                ativo INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bloqueios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                colaborador_id INTEGER NOT NULL,
                data_inicio TEXT NOT NULL,
                data_fim TEXT NOT NULL,
                motivo TEXT,
                carregamento_id INTEGER,
                FOREIGN KEY(colaborador_id) REFERENCES colaboradores(id)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rotas_semanais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dia_semana TEXT NOT NULL,
                rota TEXT NOT NULL,
                destino TEXT,
                observacao TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rotas_suprimidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                rota TEXT NOT NULL,
                UNIQUE(data, rota)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS escala_cd (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                motorista_id INTEGER,
                ajudante_id INTEGER,
                observacao TEXT,
                FOREIGN KEY(motorista_id) REFERENCES colaboradores(id),
                FOREIGN KEY(ajudante_id) REFERENCES colaboradores(id)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ajustes_rotas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                carregamento_id INTEGER NOT NULL,
                data_ajuste TEXT NOT NULL,
                duracao_anterior INTEGER NOT NULL,
                duracao_nova INTEGER NOT NULL,
                observacao_ajuste TEXT,
                FOREIGN KEY(carregamento_id) REFERENCES carregamentos(id)
            );
            """
        )
        cur.execute("PRAGMA table_info(carregamentos);")
        colunas_carregamentos = {row[1] for row in cur.fetchall()}
        if "revisado" not in colunas_carregamentos:
            cur.execute("ALTER TABLE carregamentos ADD COLUMN revisado INTEGER NOT NULL DEFAULT 0;")
        cur.execute("PRAGMA table_info(folgas);")
        colunas_folgas = {row[1] for row in cur.fetchall()}
        if "data_saida" not in colunas_folgas:
            cur.execute("ALTER TABLE folgas ADD COLUMN data_saida TEXT;")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_colaboradores_funcao_ativo ON colaboradores (funcao, ativo);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_carregamentos_data ON carregamentos (data);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_carregamentos_data_rota ON carregamentos (data, rota);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_carregamentos_data_saida ON carregamentos (data_saida);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_folgas_data ON folgas (data);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_folgas_data_saida ON folgas (data_saida);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ferias_periodo ON ferias (data_inicio, data_fim);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_oficinas_data ON oficinas (data);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_oficinas_data_saida ON oficinas (data_saida);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_escala_cd_data ON escala_cd (data);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bloqueios_periodo ON bloqueios (data_inicio, data_fim);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bloqueios_carregamento ON bloqueios (carregamento_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rotas_semanais_dia ON rotas_semanais (dia_semana);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rotas_suprimidas_data ON rotas_suprimidas (data);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ajustes_rotas_carregamento ON ajustes_rotas (carregamento_id, id);")
        conn.commit()
