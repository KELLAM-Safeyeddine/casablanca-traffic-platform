"""Contrat immuable des filtres et sérialisation URL validée."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Filters:
    """Une sélection vide reste vide, y compris après partage du lien."""

    communes: tuple[int, ...]
    days: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7)
    hours: tuple[int, int] = (0, 23)
    period: str = "all"

    @property
    def effective_days(self) -> tuple[int, ...]:
        """Intersecter les jours avec la période, sans remplacement silencieux."""
        allowed = range(1, 6) if self.period == "weekday" else range(6, 8)
        return self.days if self.period == "all" else tuple(d for d in self.days if d in allowed)

    def parameters(self) -> dict[str, object]:
        """Fournir uniquement des paramètres liés, jamais du SQL provenant de l'URL."""
        return {
            "communes": list(self.communes),
            "days": list(self.effective_days),
            "start": self.hours[0],
            "end": self.hours[1],
        }


def parse_ids(value: str, allowed: tuple[int, ...]) -> tuple[int, ...]:
    """Valider une liste d'entiers contre un catalogue ; rejeter les IDs inconnus."""
    if value in {"", "none"}:
        return ()
    parsed = tuple(sorted({int(part) for part in value.split(",")}))
    if not set(parsed).issubset(allowed):
        raise ValueError("Unknown filter identifier")
    return parsed


def decode(parameters: Mapping[str, str], catalog: tuple[int, ...]) -> Filters:
    """Décoder une URL ; laisser le caller afficher un avertissement si invalide."""
    communes = (
        catalog
        if parameters.get("communes", "all") == "all"
        else parse_ids(parameters["communes"], catalog)
    )
    days = parse_ids(parameters.get("days", "1,2,3,4,5,6,7"), tuple(range(1, 8)))
    hours = tuple(int(v) for v in parameters.get("hours", "0,23").split(","))
    if len(hours) != 2 or not 0 <= hours[0] <= hours[1] <= 23:
        raise ValueError("Invalid hours")
    period = parameters.get("period", "all")
    if period not in {"all", "weekday", "weekend"}:
        raise ValueError("Invalid period")
    return Filters(communes, days, (hours[0], hours[1]), period)


def encode(filters: Filters, catalog: tuple[int, ...]) -> dict[str, str]:
    """Préserver la différence toutes/aucune dans une URL compacte."""
    return {
        "communes": "all"
        if filters.communes == catalog
        else ",".join(map(str, filters.communes)) or "none",
        "days": ",".join(map(str, filters.days)) or "none",
        "hours": ",".join(map(str, filters.hours)),
        "period": filters.period,
    }
