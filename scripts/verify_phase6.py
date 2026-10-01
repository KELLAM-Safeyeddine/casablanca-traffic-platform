"""Vérifier les marts par un oracle pandas indépendant et des tests SQL réels."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
import psycopg2
from dotenv import dotenv_values
from psycopg2 import sql
from psycopg2.extensions import connection

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_phase5 import snapshot as core_snapshot  # noqa: E402
from src.load.marts import MART_TABLES, SQL_FILES, build_marts  # noqa: E402


def read_frame(database: connection, statement: str) -> pd.DataFrame:
    """Lire un résultat sans dépendre d'un adaptateur pandas DBAPI non supporté."""
    with database.cursor() as query:
        query.execute(statement)
        return pd.DataFrame(query.fetchall(), columns=[column.name for column in query.description])


def mart_snapshot(database: connection) -> dict:
    """Comparer comptes et contenu complet des tables analytiques."""
    result = {}
    with database.cursor() as query:
        for table in MART_TABLES:
            query.execute(
                sql.SQL(
                    "SELECT count(*), md5(string_agg(hash, '' ORDER BY hash)) FROM "
                    "(SELECT md5(row_to_json(t)::text) hash FROM public.{} t) hashes"
                ).format(sql.Identifier(table))
            )
            count, digest = query.fetchone()
            result[table] = {"rows": count, "digest": digest}
    return result


def aggregate_oracle(facts: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Calculer le p95 depuis les observations, sans lire les agrégats SQL."""
    return facts.groupby(keys, as_index=False).agg(
        measurement_count=("tti", "size"),
        tti_mean=("tti", "mean"),
        tti_p95=("tti", lambda values: values.quantile(0.95, interpolation="linear")),
        speed_mean_kmh=("speed_kmh", "mean"),
        tti_gap_count=("tti_gap_flag", "sum"),
    )


def compare(actual: pd.DataFrame, expected: pd.DataFrame, keys: list[str]) -> None:
    """Tolérer seulement les arrondis flottants, avec toutes les clés et colonnes."""
    columns = expected.columns.tolist()
    pd.testing.assert_frame_equal(
        actual[columns].sort_values(keys).reset_index(drop=True),
        expected.sort_values(keys).reset_index(drop=True),
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def verify_oracle(database: connection) -> dict:
    """Réconcilier chaque cellule des quatre marts avec les 73 920 faits."""
    facts = read_frame(
        database,
        """SELECT p.commune_id, f.trajectory_id, f.day_of_week,
        f.hour, f.tti, f.speed_kmh, f.tti_gap_flag, d.is_weekend
        FROM public.fact_travel_time f JOIN public.dim_trajectory t USING (trajectory_id)
        JOIN public.dim_point p ON p.point_id=t.origin_point_id
        JOIN public.dim_time d USING (day_of_week, hour)
        ORDER BY f.trajectory_id, f.day_of_week, f.hour""",
    )
    assert len(facts) == 73920
    hourly = aggregate_oracle(facts, ["commune_id", "day_of_week", "hour"])
    actual = read_frame(database, "SELECT * FROM public.mart_commune_hourly_congestion")
    compare(actual, hourly, ["commune_id", "day_of_week", "hour"])
    assert hourly["measurement_count"].eq(20).all()
    maxima = hourly.groupby(["commune_id", "day_of_week"])["tti_mean"].transform("max")
    peaks = hourly.loc[hourly["tti_mean"] == maxima].drop(
        columns=["speed_mean_kmh", "tti_gap_count"]
    )
    compare(
        read_frame(database, "SELECT * FROM public.mart_peak_hours"),
        peaks,
        ["commune_id", "day_of_week", "hour"],
    )
    groups = ["commune_id", "is_weekend"]
    weekend = aggregate_oracle(facts, groups).drop(columns="tti_gap_count")
    days = facts.groupby(groups, as_index=False).agg(day_count=("day_of_week", "nunique"))
    weekend = weekend.merge(days, on=groups, validate="one_to_one")
    compare(read_frame(database, "SELECT * FROM public.mart_weekday_vs_weekend"), weekend, groups)
    assert weekend.loc[~weekend["is_weekend"], "measurement_count"].eq(2400).all()
    assert weekend.loc[weekend["is_weekend"], "measurement_count"].eq(960).all()
    features = read_frame(database, "SELECT * FROM public.mart_commune_features")
    compare(features, aggregate_oracle(facts, ["commune_id"]), ["commune_id"])
    attributes = read_frame(database, "SELECT * FROM public.dim_commune")
    compare(features, attributes, ["commune_id"])
    print("OK oracle pandas : chaque clé et KPI des quatre marts concorde avec CORE", flush=True)
    return {
        "facts": len(facts),
        "hourly_groups": len(hourly),
        "peak_rows": len(peaks),
        "weekend_groups": len(weekend),
        "feature_rows": len(features),
    }


def verify_peak_ties(database: connection) -> None:
    """Exécuter le SQL de pointe sur des données temporaires avec une égalité."""
    with database.cursor() as query:
        query.execute(
            "CREATE TEMP TABLE mart_commune_hourly_congestion "
            "(commune_id int, day_of_week int, hour int, tti_mean float8, "
            "tti_p95 float8, measurement_count int) ON COMMIT DROP"
        )
        query.execute(
            "CREATE TEMP TABLE mart_peak_hours "
            "(commune_id int, day_of_week int, hour int, tti_mean float8, "
            "tti_p95 float8, measurement_count int) ON COMMIT DROP"
        )
        query.execute(
            "INSERT INTO pg_temp.mart_commune_hourly_congestion VALUES "
            "(1,1,7,2,3,20),(1,1,8,2,4,20),(1,1,9,1,2,20),(2,1,7,1,1,20)"
        )
        statement = (ROOT / "sql/marts/02_peak_hours.sql").read_text(encoding="utf-8")
        query.execute(statement.replace("public.", "pg_temp."))
        query.execute(
            "SELECT commune_id,hour FROM pg_temp.mart_peak_hours ORDER BY commune_id,hour"
        )
        assert query.fetchall() == [(1, 7), (1, 8), (2, 7)]
    database.rollback()  # les seules écritures sont dans les tables temporaires
    print("OK SQL de pointe : égalités conservées sur échantillon temporaire", flush=True)


def verify_rollback(database: connection) -> None:
    """Injecter une panne après les remplacements et vérifier les quatre tables."""
    before = mart_snapshot(database)
    with TemporaryDirectory(prefix="phase6_sql_") as temporary:
        directory = Path(temporary)
        (directory / "sql/marts").mkdir(parents=True)
        for name in SQL_FILES:
            statement = (ROOT / "sql/marts" / name).read_text(encoding="utf-8")
            if name == SQL_FILES[-1]:
                statement += "\nSELECT 1/0;\n"
            (directory / "sql/marts" / name).write_text(statement, encoding="utf-8")
        with patch("src.load.marts.ROOT", directory):
            try:
                build_marts(database)
            except psycopg2.errors.DivisionByZero:
                pass
            else:
                raise AssertionError("La panne SQL devait interrompre la reconstruction")
    assert mart_snapshot(database) == before
    print("OK panne SQL : rollback des quatre marts, contenu conservé", flush=True)


def main() -> None:
    """Construire deux fois, comparer à CORE et tester les cas limites SQL."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    settings = dotenv_values(ROOT / ".env")
    database = psycopg2.connect(
        host="127.0.0.1",
        port=settings["POSTGRES_PORT"],
        dbname="traffic",
        user="traffic",
        password=settings["TRAFFIC_DB_PASSWORD"],
    )
    try:
        core_before = core_snapshot(database)
        counts = build_marts(database)
        before = mart_snapshot(database)
        assert build_marts(database) == counts and mart_snapshot(database) == before
        oracle = verify_oracle(database)
        verify_peak_ties(database)
        verify_rollback(database)
        assert core_snapshot(database) == core_before
        report = {
            "counts": counts,
            "snapshots": before,
            "oracle": oracle,
            "idempotent_content": True,
            "peak_ties_verified": True,
            "rollback_verified": True,
            "core_unchanged": True,
        }
        (ROOT / "docs/phase6_verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("OK marts reconstruits sans doublon ; CORE inchangé", flush=True)
    finally:
        database.close()


if __name__ == "__main__":
    main()
