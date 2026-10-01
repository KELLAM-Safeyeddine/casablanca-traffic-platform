"""Contrats pandera des douze tables source, sans mutation du RAW."""

import numpy as np
import pandas as pd
import pandera.pandas as pa

INTEGER = pa.Check(lambda values: values.mod(1).eq(0), name="integer_value")
FINITE = pa.Check(lambda values: np.isfinite(values), name="finite_value")
LATITUDE = (33.3, 33.8)
LONGITUDE = (-7.9, -7.2)
URBAN_COLUMNS = {
    1: ["Population size", "Household", "Density"],
    2: ["Tram-Station", "Bus-Station"],
    3: ["N° of Primary roads", "N° of Secondery roads", "N° of Highways"],
    4: [
        "Region area (m²)",
        "Parking area (m²)",
        "Industrial area  (m²)",
        "Parks area  (m²)",
        "Residential area (m²)",
        "University/ Institution area (m²)",
        "Number of Commercial Buildings",
    ],
}


def numeric(*checks: pa.Check) -> pa.Column:
    """Exiger un nombre fini et présent ; aucun arrondi implicite."""
    return pa.Column(float, checks=[FINITE, *checks], nullable=False)


def source_schema(number: int, replay: bool = False) -> pa.DataFrameSchema:
    """Construire le contrat de la table, avec unicité au grain source."""
    if number not in range(12):
        raise ValueError("Table source attendue : 0 à 11")
    traffic = number >= 5
    commune, zipcode = ("commune", "zip") if traffic else ("Commune", "ZIP code")
    columns = {
        commune: pa.Column(str, pa.Check.str_length(min_value=1)),
        zipcode: numeric(INTEGER, pa.Check.in_range(10000, 99999)),
    }
    unique = [commune, zipcode]
    if number == 0:
        columns.update(
            {
                "Index": numeric(INTEGER, pa.Check.in_range(0, 109)),
                "Latitude": numeric(pa.Check.in_range(*LATITUDE)),
                "Longitude": numeric(pa.Check.in_range(*LONGITUDE)),
            }
        )
        unique = ["Index"]
    elif not traffic:
        for name in URBAN_COLUMNS[number]:
            checks = [pa.Check.ge(0)]
            if number in (2, 3) or name == "Number of Commercial Buildings":
                checks.append(INTEGER)
            if name == "Region area (m²)":
                checks = [pa.Check.gt(0)]
            columns[name] = numeric(*checks)
    else:
        for role in ("origin", "dest"):
            columns[f"{role}_index"] = numeric(INTEGER, pa.Check.ge(0))
            columns[f"{role}_lat"] = numeric(pa.Check.in_range(*LATITUDE))
            columns[f"{role}_lon"] = numeric(pa.Check.in_range(*LONGITUDE))
        columns["distance_raw"] = numeric(pa.Check.gt(0))
        unique = ["origin_index", "dest_index"]
        if replay:
            columns.update(
                {
                    "day_of_week": numeric(INTEGER, pa.Check.eq(number - 4)),
                    "hour": numeric(INTEGER, pa.Check.in_range(0, 23)),
                    "travel_time_raw": numeric(pa.Check.gt(0)),
                    "tti_provided": numeric(pa.Check.ge(1)),
                }
            )
            unique += ["day_of_week", "hour"]
        else:
            for hour in range(24):
                columns[f"time_{hour:02d}"] = numeric(pa.Check.gt(0))
                columns[f"tti_{hour:02d}"] = numeric(pa.Check.ge(1))
    checks = [
        pa.Check(
            lambda view: len(view) == (110 if number == 0 else 22 if number < 5 else 440),
            name="expected_source_cardinality",
        )
    ]
    if number == 0:
        checks.append(
            pa.Check(
                lambda view: ~view.duplicated(["Latitude", "Longitude"], keep=False),
                name="unique_point_coordinates",
            )
        )
    return pa.DataFrameSchema(
        columns,
        unique=unique,
        checks=checks,
        report_duplicates="all",
        strict=False,
        name=f"source_table_{number}",
    )


def validation_view(frame: pd.DataFrame, schema: pa.DataFrameSchema) -> pd.DataFrame:
    """Convertir les nombres pour validation ; garder les échecs comme NaN signalables."""
    view = frame.copy().reset_index(drop=True)
    for name, column in schema.columns.items():
        if name in view and str(column.dtype) == "float64":
            values = pd.to_numeric(view[name], errors="coerce")
            # Un booléen ne doit pas devenir silencieusement un compte ou une mesure.
            booleans = view[name].map(lambda value: isinstance(value, bool | np.bool_))
            view[name] = values.mask(booleans).astype(float)
    return view
