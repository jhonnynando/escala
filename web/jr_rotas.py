from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import db

SOURCE_NAME = "jr_rotas"
SYNC_INTERVAL_SECONDS = 300
OPEN_DATASET_URL = (
    "https://raw.githubusercontent.com/joaopbini/feriados-brasil/"
    "master/dados/feriados/municipal/json/{year}.json"
)
WEEKDAYS = {
    0: "segunda",
    1: "terca",
    2: "quarta",
    3: "quinta",
    4: "sexta",
    5: "sabado",
    6: "domingo",
}
WEEKDAY_NUMBERS = {value: key for key, value in WEEKDAYS.items()}


class JRRotasError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncResult:
    configured: bool
    checked: bool = False
    changed: bool = False
    added: int = 0
    updated: int = 0
    removed: int = 0
    total: int = 0
    synced_at: datetime | None = None
    message: str = ""


@dataclass(frozen=True)
class HolidayAlert:
    city: str
    holiday_date: date
    holiday_type: str
    holiday_name: str
    route_code: str
    destination: str
    departure_date: date
    return_date: date


_SYNC_LOCK = Lock()
_LAST_SYNC_AT = 0.0
_LAST_SYNC_RESULT: SyncResult | None = None


def _secret(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st

        secret = st.secrets.get(name)
        return str(secret) if secret else None
    except Exception:  # noqa: BLE001 - Streamlit usa exceções próprias opcionais.
        return None


def source_database_url() -> str | None:
    value = db._clean_database_url(_secret("JR_ROTAS_DATABASE_URL"))
    if value and value.startswith("postgresql+psycopg://"):
        value = value.replace("postgresql+psycopg://", "postgresql://", 1)
    if value and value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql://", 1)
    if value and not value.startswith("postgresql://"):
        raise JRRotasError("JR_ROTAS_DATABASE_URL deve ser uma URL PostgreSQL/Neon.")
    return value


def integration_configured() -> bool:
    try:
        return bool(source_database_url())
    except JRRotasError:
        return False


def _source_connection(url: str):
    if db.psycopg is None:
        raise JRRotasError(
            "O driver PostgreSQL necessário para o JR Rotas não está instalado."
        )
    try:
        connection = db.psycopg.connect(
            url,
            autocommit=True,
            connect_timeout=int(os.getenv("JR_ROTAS_DB_CONNECT_TIMEOUT", "8")),
            row_factory=db.pg_rows.dict_row if db.pg_rows else None,
        )
        connection.execute("SET default_transaction_read_only = on")
        return connection
    except Exception as exc:
        raise JRRotasError("Não foi possível consultar o banco do JR Rotas.") from exc


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _source_key(weekday: int, code: str) -> str:
    return f"{weekday}:{_clean_text(code).upper()}"


def _route_hash(item: dict) -> str:
    payload = {
        "day": item["dia_semana"],
        "code": item["rota"],
        "destination": item["destino"],
        "notes": item["observacao"],
        "position": item["ordem"],
        "cities": item["cidades"],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_cities(value: Any) -> list[dict]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = []
    result: list[dict] = []
    seen: set[str] = set()
    for raw in value or []:
        if not isinstance(raw, dict):
            continue
        original = _clean_text(raw.get("city_original"))
        municipality = _clean_text(raw.get("municipality_name"))
        ibge_code = _clean_text(raw.get("ibge_code"))
        state = _clean_text(raw.get("state") or "MG").upper()[:2]
        key = ibge_code or (municipality or original).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "city_original": original,
                "municipality_name": municipality,
                "state": state or "MG",
                "ibge_code": ibge_code,
            }
        )
    return result


def _matrix_day_notes(value: Any) -> dict[int, str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(value, dict):
        return {}

    notes_by_day: dict[int, str] = {}
    route_pattern = re.compile(r"\(?\s*R\s*\.\s*\d+\s*\)?", re.IGNORECASE)
    for weekday in range(7):
        values = value.get(str(weekday), value.get(weekday, []))
        if not isinstance(values, list):
            continue
        current_route = False
        notes: list[str] = []
        for raw_value in values:
            text = _clean_text(raw_value).lstrip("!* ").strip()
            if not text:
                continue
            if route_pattern.search(text):
                current_route = True
                continue
            normalized = text.casefold()
            if normalized.startswith(("extra bh", "coleta ")):
                current_route = False
                notes.append(text)
                continue
            if not current_route and text.casefold() not in {
                "cidade",
                "cidades",
                "rota",
                "rotas",
            }:
                notes.append(text)
        if notes:
            notes_by_day[weekday] = " · ".join(dict.fromkeys(notes))
    return notes_by_day


def _fetch_source_routes(url: str) -> list[dict]:
    query = """
        SELECT
            p.weekday,
            r.code,
            COALESCE(NULLIF(BTRIM(p.display_name), ''), r.name) AS destination,
            p.position,
            COALESCE(
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'city_original', c.city_original,
                        'municipality_name', c.municipality_name,
                        'state', c.state,
                        'ibge_code', c.ibge_code
                    ) ORDER BY c.position
                ) FILTER (WHERE c.id IS NOT NULL),
                '[]'::json
            ) AS cities
        FROM route_weekday_profiles p
        JOIN routes r ON r.id = p.route_id
        LEFT JOIN route_weekday_cities c ON c.profile_id = p.id
        WHERE r.active IS TRUE AND p.weekday BETWEEN 0 AND 6
        GROUP BY p.weekday, r.code, r.name, p.display_name, p.position
        ORDER BY p.weekday, p.position, r.code;
    """
    try:
        with _source_connection(url) as connection, connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.execute(
                "SELECT value FROM app_settings WHERE key = %s LIMIT 1;",
                ("route_weekday_matrix_columns",),
            )
            setting = cursor.fetchone()
    except JRRotasError:
        raise
    except Exception as exc:
        raise JRRotasError(
            "O esquema de rotas do banco de origem não está disponível."
        ) from exc

    notes_by_day = _matrix_day_notes(setting.get("value") if setting else None)
    routes: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        weekday = int(row["weekday"])
        code = _clean_text(row["code"])
        if weekday not in WEEKDAYS or not code:
            continue
        source_id = _source_key(weekday, code)
        if source_id in seen:
            continue
        seen.add(source_id)
        item = {
            "origem_id": source_id,
            "dia_semana": WEEKDAYS[weekday],
            "rota": code,
            "destino": _clean_text(row["destination"]),
            "observacao": notes_by_day.get(weekday, ""),
            "ordem": int(row.get("position") or 0),
            "cidades": _normalize_cities(row.get("cities")),
        }
        item["origem_hash"] = _route_hash(item)
        routes.append(item)
    if not routes:
        raise JRRotasError("O JR Rotas não possui rotas semanais para sincronizar.")
    return routes


def _apply_snapshot(routes: list[dict]) -> tuple[int, int, int]:
    now_iso = datetime.now(timezone.utc).isoformat()
    added = updated = removed = 0
    source_ids = {item["origem_id"] for item in routes}
    managed_days = sorted({item["dia_semana"] for item in routes})

    with db.get_connection(dict_rows=True) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, origem_id, origem_hash
            FROM rotas_semanais
            WHERE origem = ?;
            """,
            (SOURCE_NAME,),
        )
        existing = {row["origem_id"]: dict(row) for row in cursor.fetchall()}

        for item in routes:
            current = existing.get(item["origem_id"])
            cities_json = json.dumps(
                item["cidades"], ensure_ascii=False, separators=(",", ":")
            )
            values = (
                item["dia_semana"],
                item["rota"],
                item["destino"],
                item["observacao"],
                SOURCE_NAME,
                item["origem_id"],
                item["origem_hash"],
                item["ordem"],
                cities_json,
                now_iso,
            )
            if current is None:
                cursor.execute(
                    """
                    INSERT INTO rotas_semanais (
                        dia_semana, rota, destino, observacao, origem, origem_id,
                        origem_hash, ordem, cidades_json, sincronizado_em
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    values,
                )
                added += 1
            elif current.get("origem_hash") != item["origem_hash"]:
                cursor.execute(
                    """
                    UPDATE rotas_semanais
                    SET dia_semana = ?, rota = ?, destino = ?, observacao = ?,
                        origem = ?, origem_id = ?, origem_hash = ?, ordem = ?,
                        cidades_json = ?, sincronizado_em = ?
                    WHERE id = ?;
                    """,
                    (*values, current["id"]),
                )
                updated += 1

        stale_ids = [
            row["id"]
            for source_id, row in existing.items()
            if source_id not in source_ids
        ]
        if stale_ids:
            placeholders = ",".join("?" for _ in stale_ids)
            cursor.execute(
                f"DELETE FROM rotas_semanais WHERE id IN ({placeholders});",
                tuple(stale_ids),
            )
            removed += len(stale_ids)

        # A origem é oficial: ao ativar a integração, elimina registros locais
        # dos dias administrados pelo JR Rotas para não manter cópias divergentes.
        if managed_days:
            placeholders = ",".join("?" for _ in managed_days)
            cursor.execute(
                f"""
                DELETE FROM rotas_semanais
                WHERE COALESCE(origem, 'local') <> ?
                  AND dia_semana IN ({placeholders});
                """,
                (SOURCE_NAME, *managed_days),
            )
            removed += max(int(cursor.rowcount or 0), 0)
        connection.commit()
    if not db.USE_POSTGRES:
        connection.close()
    return added, updated, removed


def sync_weekly_routes(force: bool = False) -> SyncResult:
    global _LAST_SYNC_AT, _LAST_SYNC_RESULT

    url = source_database_url()
    if not url:
        return SyncResult(
            configured=False,
            message="Configure JR_ROTAS_DATABASE_URL para ativar a integração.",
        )

    now = time.monotonic()
    if not force and _LAST_SYNC_RESULT and now - _LAST_SYNC_AT < SYNC_INTERVAL_SECONDS:
        return _LAST_SYNC_RESULT

    with _SYNC_LOCK:
        now = time.monotonic()
        if (
            not force
            and _LAST_SYNC_RESULT
            and now - _LAST_SYNC_AT < SYNC_INTERVAL_SECONDS
        ):
            return _LAST_SYNC_RESULT
        routes = _fetch_source_routes(url)
        added, updated, removed = _apply_snapshot(routes)
        result = SyncResult(
            configured=True,
            checked=True,
            changed=bool(added or updated or removed),
            added=added,
            updated=updated,
            removed=removed,
            total=len(routes),
            synced_at=datetime.now(timezone.utc),
            message="Rotas sincronizadas com o JR Rotas.",
        )
        _LAST_SYNC_AT = time.monotonic()
        _LAST_SYNC_RESULT = result
        return result


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        day, month, year = (int(part) for part in text.split("/"))
        return date(year, month, day)


def trip_duration_days(observation: str | None) -> int:
    match = re.search(r"\bROTA\s+(\d+)\s+DIAS?\b", observation or "", re.IGNORECASE)
    return max(1, int(match.group(1))) if match else 1


@lru_cache(maxsize=6)
def _general_holidays(year: int, state: str) -> tuple[dict, ...]:
    try:
        import holidays as python_holidays
    except ImportError as exc:
        raise JRRotasError("A biblioteca de feriados não está instalada.") from exc

    national = python_holidays.country_holidays("BR", years=[year])
    state_calendar = python_holidays.country_holidays("BR", subdiv=state, years=[year])
    result: list[dict] = []
    for holiday_date, name in national.items():
        result.append(
            {
                "date": holiday_date,
                "name": str(name),
                "type": "Nacional",
                "state": state,
            }
        )
    for holiday_date, name in state_calendar.items():
        if holiday_date not in national:
            result.append(
                {
                    "date": holiday_date,
                    "name": str(name),
                    "type": "Estadual",
                    "state": state,
                }
            )
    return tuple(result)


@lru_cache(maxsize=4)
def _municipal_dataset(year: int) -> dict[str, tuple[dict, ...]]:
    request = Request(
        OPEN_DATASET_URL.format(year=year),
        headers={"User-Agent": "JR-Escala/1.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise JRRotasError(
            f"Não foi possível consultar os feriados municipais de {year}."
        ) from exc
    if not isinstance(payload, list):
        raise JRRotasError("A fonte de feriados municipais retornou dados inválidos.")
    grouped: dict[str, list[dict]] = {}
    for item in payload:
        code = _clean_text(item.get("codigo_ibge"))
        if not code:
            continue
        grouped.setdefault(code, []).append(
            {
                "date": _parse_date(item.get("data")),
                "name": _clean_text(item.get("nome")) or "Feriado Municipal",
                "type": (_clean_text(item.get("tipo")) or "Municipal").title(),
            }
        )
    return {key: tuple(value) for key, value in grouped.items()}


def _source_cached_holidays(
    url: str, years: set[int], city_keys: set[str]
) -> list[dict]:
    if not years or not city_keys:
        return []
    query = """
        SELECT city_key, city, state, ibge_code, date, holiday_name, holiday_type
        FROM holiday_cache
        WHERE year = ANY(%s) AND city_key = ANY(%s)
        ORDER BY date;
    """
    try:
        with _source_connection(url) as connection, connection.cursor() as cursor:
            cursor.execute(query, (sorted(years), sorted(city_keys)))
            return [dict(row) for row in cursor.fetchall()]
    except Exception:  # noqa: BLE001 - cache remoto é um fallback opcional.
        # O cache da origem é complementar. A ausência dele não impede a
        # verificação nacional/estadual ou o dataset municipal aberto.
        return []


def _decode_cities(route: dict) -> list[dict]:
    cities = _normalize_cities(route.get("cidades_json") or route.get("cidades") or [])
    if cities:
        return cities
    destination = _clean_text(route.get("destino"))
    if not destination:
        return []
    return [
        {
            "city_original": destination,
            "municipality_name": destination,
            "state": "MG",
            "ibge_code": "",
        }
    ]


def verify_route_holidays(
    routes: Iterable[dict], reference_date: date
) -> tuple[list[HolidayAlert], list[str]]:
    route_list = list(routes)
    monday = reference_date - timedelta(days=reference_date.weekday())
    prepared: list[tuple[dict, date, date, list[dict]]] = []
    years: set[int] = set()
    states: set[str] = set()
    city_keys: set[str] = set()

    for route in route_list:
        weekday = WEEKDAY_NUMBERS.get(_clean_text(route.get("dia_semana")).casefold())
        if weekday is None:
            continue
        departure = monday + timedelta(days=weekday)
        duration = trip_duration_days(route.get("observacao"))
        return_date = departure + timedelta(days=duration - 1)
        cities = _decode_cities(route)
        prepared.append((route, departure, return_date, cities))
        for offset in range(duration):
            years.add((departure + timedelta(days=offset)).year)
        for city in cities:
            state = city.get("state") or "MG"
            states.add(state)
            city_keys.add(
                city.get("ibge_code")
                or _clean_text(
                    city.get("municipality_name") or city.get("city_original")
                ).casefold()
            )

    general: dict[tuple[int, str], tuple[dict, ...]] = {}
    for year in years:
        for state in states or {"MG"}:
            general[(year, state)] = _general_holidays(year, state)

    url = source_database_url()
    cached = _source_cached_holidays(url, years, city_keys) if url else []
    cached_by_key: dict[str, list[dict]] = {}
    for item in cached:
        cached_by_key.setdefault(str(item.get("city_key") or ""), []).append(
            {
                "date": _parse_date(item["date"]),
                "name": _clean_text(item.get("holiday_name")),
                "type": _clean_text(item.get("holiday_type")) or "Municipal",
            }
        )

    municipal_by_year: dict[int, dict[str, tuple[dict, ...]]] = {}
    warnings: list[str] = []
    if any(city.get("ibge_code") for _, _, _, cities in prepared for city in cities):
        for year in years:
            try:
                municipal_by_year[year] = _municipal_dataset(year)
            except JRRotasError as exc:
                warnings.append(str(exc))

    alerts: list[HolidayAlert] = []
    seen: set[tuple] = set()

    def append_alert(
        route: dict, departure: date, return_date: date, city: str, holiday: dict
    ) -> None:
        holiday_date = _parse_date(holiday["date"])
        key = (
            route.get("origem_id") or route.get("id"),
            holiday_date,
            city.casefold(),
            _clean_text(holiday.get("name")).casefold(),
            _clean_text(holiday.get("type")).casefold(),
        )
        if key in seen:
            return
        seen.add(key)
        alerts.append(
            HolidayAlert(
                city=city,
                holiday_date=holiday_date,
                holiday_type=_clean_text(holiday.get("type")) or "Feriado",
                holiday_name=_clean_text(holiday.get("name")) or "Feriado",
                route_code=_clean_text(route.get("rota")),
                destination=_clean_text(route.get("destino")),
                departure_date=departure,
                return_date=return_date,
            )
        )

    for route, departure, return_date, cities in prepared:
        trip_dates = {
            departure + timedelta(days=offset)
            for offset in range((return_date - departure).days + 1)
        }
        route_states = {city.get("state") or "MG" for city in cities} or {"MG"}
        for state in route_states:
            for year in {day.year for day in trip_dates}:
                for holiday in general.get((year, state), ()):
                    if holiday["date"] not in trip_dates:
                        continue
                    label = (
                        "Todas as cidades"
                        if holiday["type"] == "Nacional"
                        else f"Estado de {state}"
                    )
                    append_alert(route, departure, return_date, label, holiday)

        for city in cities:
            code = city.get("ibge_code") or ""
            city_name = _clean_text(
                city.get("municipality_name") or city.get("city_original")
            )
            city_key = code or city_name.casefold()
            entries: list[dict] = []
            for year in {day.year for day in trip_dates}:
                entries.extend(municipal_by_year.get(year, {}).get(code, ()))
            entries.extend(cached_by_key.get(city_key, ()))
            for holiday in entries:
                if holiday["date"] in trip_dates and _clean_text(
                    holiday.get("type")
                ).casefold() not in {"nacional", "estadual"}:
                    append_alert(route, departure, return_date, city_name, holiday)

    alerts.sort(key=lambda item: (item.holiday_date, item.route_code, item.city))
    return alerts, sorted(set(warnings))
