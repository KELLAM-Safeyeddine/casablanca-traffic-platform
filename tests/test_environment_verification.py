"""Régressions du contrôle d'import Airflow face aux logs préfixant le JSON."""

import pytest

from scripts.verify_phase1 import parse_import_errors


@pytest.mark.parametrize("output", ["[]", "[2026-10-01] INFO plugin\n[]\n"])
def test_empty_errors_with_or_without_logs(output: str) -> None:
    """Ne pas interpréter l'horodatage des logs comme le tableau d'erreurs."""
    assert parse_import_errors(output) == []


def test_real_import_error_is_preserved() -> None:
    """Un résultat non vide doit rester visible pour faire échouer la validation."""
    output = '[2026-10-01] INFO plugin\n[{"filename": "dag.py", "stacktrace": "oops"}]'
    assert parse_import_errors(output) == [{"filename": "dag.py", "stacktrace": "oops"}]


def test_missing_json_fails() -> None:
    """Une CLI cassée ne doit pas produire un succès trompeur."""
    with pytest.raises(ValueError, match="tableau JSON valide"):
        parse_import_errors("[2026-10-01] ERROR command failed")
