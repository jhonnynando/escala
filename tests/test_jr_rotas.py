import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from web import db, jr_rotas


class TripDurationTests(unittest.TestCase):
    def test_reads_multi_day_observation(self):
        self.assertEqual(jr_rotas.trip_duration_days("ROTA 3 DIAS"), 3)
        self.assertEqual(jr_rotas.trip_duration_days("ROTA 1 DIA (BATE E VOLTA)"), 1)
        self.assertEqual(jr_rotas.trip_duration_days("observação livre"), 1)

    def test_extracts_only_day_level_operational_notes(self):
        notes = jr_rotas._matrix_day_notes(
            {
                "0": [
                    "Observação antes das rotas",
                    "ITAÚNA (R.40)",
                    "Mateus Leme",
                    "COLETA ESPECIAL",
                    "Retorno após as 16h",
                ]
            }
        )
        self.assertEqual(
            notes[0],
            "Observação antes das rotas · COLETA ESPECIAL · Retorno após as 16h",
        )

    def test_holiday_on_last_day_of_trip_is_reported(self):
        routes = [
            {
                "id": 1,
                "origem_id": "0:R.40",
                "dia_semana": "segunda",
                "rota": "R.40",
                "destino": "Itaúna",
                "observacao": "ROTA 3 DIAS",
                "cidades_json": json.dumps(
                    [
                        {
                            "city_original": "Itaúna",
                            "municipality_name": "Itaúna",
                            "state": "MG",
                            "ibge_code": "3133808",
                        }
                    ]
                ),
            }
        ]
        municipal = {
            "3133808": (
                {
                    "date": date(2026, 9, 30),
                    "name": "Feriado local",
                    "type": "Municipal",
                },
            )
        }
        with (
            mock.patch.object(jr_rotas, "_general_holidays", return_value=()),
            mock.patch.object(jr_rotas, "_municipal_dataset", return_value=municipal),
            mock.patch.object(jr_rotas, "source_database_url", return_value=None),
        ):
            alerts, warnings = jr_rotas.verify_route_holidays(routes, date(2026, 9, 28))

        self.assertFalse(warnings)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].holiday_date, date(2026, 9, 30))
        self.assertEqual(alerts[0].return_date, date(2026, 9, 30))


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.patches = (
            mock.patch.object(db, "DB_PATH", self.db_path),
            mock.patch.object(db, "USE_POSTGRES", False),
        )
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        db.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def route(code: str, destination: str, source_id: str) -> dict:
        item = {
            "origem_id": source_id,
            "dia_semana": "segunda",
            "rota": code,
            "destino": destination,
            "observacao": "",
            "ordem": 0,
            "cidades": [],
        }
        item["origem_hash"] = jr_rotas._route_hash(item)
        return item

    def test_snapshot_updates_incrementally_without_duplicates(self):
        first = self.route("R.40", "Itaúna", "0:R.40")
        self.assertEqual(jr_rotas._apply_snapshot([first]), (1, 0, 0))
        self.assertEqual(jr_rotas._apply_snapshot([first]), (0, 0, 0))

        changed = self.route("R.40", "Itaúna e região", "0:R.40")
        second = self.route("R.41", "Pará de Minas", "0:R.41")
        self.assertEqual(jr_rotas._apply_snapshot([changed, second]), (1, 1, 0))
        self.assertEqual(jr_rotas._apply_snapshot([second]), (0, 0, 1))

        with db.get_connection(dict_rows=True) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT rota, destino, origem FROM rotas_semanais;")
            rows = [dict(row) for row in cursor.fetchall()]
        connection.close()
        self.assertEqual(
            rows, [{"rota": "R.41", "destino": "Pará de Minas", "origem": "jr_rotas"}]
        )


if __name__ == "__main__":
    unittest.main()
