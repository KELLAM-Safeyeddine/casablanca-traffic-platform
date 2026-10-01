"""Construire des dimensions déterministes à partir des références validées."""

import pandas as pd

from src.transform.normalize import commune_key

ATTRIBUTES = {
    1: {"Population size": "population", "Household": "households", "Density": "density_source"},
    2: {"Tram-Station": "tram_stations", "Bus-Station": "bus_stations"},
    3: {
        "N° of Primary roads": "primary_roads",
        "N° of Secondery roads": "secondary_roads",
        "N° of Highways": "highways",
    },
    4: {
        "Region area (m²)": "region_area_m2",
        "Parking area (m²)": "parking_area_m2",
        "Industrial area  (m²)": "industrial_area_m2",
        "Parks area  (m²)": "parks_area_m2",
        "Residential area (m²)": "residential_area_m2",
        "University/ Institution area (m²)": "university_area_m2",
        "Number of Commercial Buildings": "commercial_buildings",
    },
}


def dimension_frames(tables: dict[int, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Joindre les 22 communes avec contrôle 1:1 et conserver la précision numérique."""
    communes = None
    for number in range(1, 5):
        source = tables[number]
        frame = source[["Commune", "ZIP code", *ATTRIBUTES[number]]].rename(
            columns={"Commune": "nom", "ZIP code": "zip", **ATTRIBUTES[number]}
        )
        frame["nom_key"] = frame["nom"].map(commune_key)
        frame["zip"] = frame["zip"].map(lambda value: f"{int(value):05d}")
        for column in ATTRIBUTES[number].values():
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        if communes is None:
            communes = frame
        else:
            communes = communes.merge(
                frame.drop(columns="nom"),
                on=["nom_key", "zip"],
                how="outer",
                validate="one_to_one",
                indicator=True,
            )
            if not communes["_merge"].eq("both").all():
                raise ValueError("Une commune manque dans une table d'attributs")
            communes = communes.drop(columns="_merge")
    if communes is None or len(communes) != 22 or communes.isna().any().any():
        raise ValueError("Les attributs des 22 communes doivent être complets")
    communes["commune_id"] = communes["zip"].astype(int)
    communes["population_density_per_km2"] = communes["population"] / (
        communes["region_area_m2"] / 1_000_000
    )
    points = tables[0][["Commune", "ZIP code", "Index", "Latitude", "Longitude"]].copy()
    points["commune_id"] = points["ZIP code"].astype(int)
    points = points.rename(columns={"Index": "point_id", "Latitude": "lat", "Longitude": "lon"})
    points["lat"], points["lon"] = points["lat"].astype(float), points["lon"].astype(float)
    return {"dim_commune": communes, "dim_point": points[["point_id", "commune_id", "lat", "lon"]]}
