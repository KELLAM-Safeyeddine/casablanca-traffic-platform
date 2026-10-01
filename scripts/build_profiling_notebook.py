"""Créer le notebook reproductible de phase 2, prévu pour le kernel CasaTraffic."""

import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Écrire des cellules de profilage sans modifier le classeur source."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic avec Python 3.11")
    markdown = nbformat.v4.new_markdown_cell
    code = nbformat.v4.new_code_cell
    cells = [
        markdown("""# Casablanca Traffic — profilage de la source

Ce notebook inspecte les **13 feuilles**, sans enregistrer le classeur et sans
charger la base. Les valeurs originales restent distinctes des corrections candidates.
Les mesures décrivent une semaine type, sans date réelle de collecte.
Sélectionner le kernel **CasaTraffic (Python 3.11)** et exécuter toutes les cellules.
"""),
        code("""import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import Markdown, display

assert sys.version_info[:2] == (3, 11)
assert Path(sys.prefix).name == 'CasaTraffic', sys.executable
ROOT = Path.cwd()
if ROOT.name == 'notebooks':
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
from src.extract.workbook_profile import SOURCE_SHA256, profile_workbook

SOURCE = ROOT / 'data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx'
initial_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert initial_hash == SOURCE_SHA256
print(sys.executable)
report, tables, measures = profile_workbook(SOURCE)
print(f"{report['sheet_count']} feuilles, {len(measures):,} observations candidates")"""),
        markdown("""## Structure et en-têtes

Le sommaire sert à la navigation et ne contient pas de mesures.
La ligne d'en-tête est détectée par son libellé Commune. Les heures 0–23 sont contrôlées
pour les deux blocs. La propagation des communes/ZIP se limite aux plages fusionnées.
"""),
        code("""overview_columns = ['sheet', 'role', 'physical_rows', 'physical_columns',
                    'header_row', 'data_rows', 'merged_ranges', 'formula_count',
                    'raw_missing_commune', 'missing_commune_after_merged_fill']
display(pd.DataFrame(report['sheets']).reindex(columns=overview_columns))"""),
        markdown("""## Profil de chaque feuille

Pour chaque table : manques par colonne, statistiques numériques et outliers IQR.
Un outlier statistique reste une observation. Le compteur `non_numeric` est normal
pour des champs texte comme Coordinates ou une formule de concaténation.
Les ZIP et les indices sont des identifiants, pas des variables continues à nettoyer.
"""),
        code("""for sheet in report['sheets']:
    display(Markdown(f"### {sheet['sheet']}"))
    number = sheet['table_number']
    if number is None:
        display(Markdown('Sommaire : 0 ligne de mesure.'))
        continue
    display(pd.DataFrame.from_dict(sheet['missing_by_column'], orient='index',
                                   columns=['missing_after_merged_fill']))
    numeric = pd.DataFrame.from_dict(sheet['numeric_by_column'], orient='index')
    display(numeric.reindex(columns=['rows', 'missing', 'non_numeric', 'min',
                                     'median', 'p95', 'max', 'iqr_outliers']))
    display(tables[number].iloc[:3, :min(8, len(tables[number].columns))])"""),
        markdown("""## Unités de distance et de temps

Règle du plan : une distance >100 est interprétée comme des mètres et divisée par 1000.
Hypothèse supplémentaire étayée par les distributions : un temps entier >=1000
a perdu son séparateur décimal et est divisé par 1000. Aucun temps n'est dérivé du TTI.
Une correction garde la valeur brute, la valeur candidate et un indicateur explicite.
"""),
        code("""routes = measures.drop_duplicates(['day_of_week', '_excel_row'])
display(pd.DataFrame({
    'distance_raw': routes.distance_raw.describe(),
    'distance_km_candidate': routes.distance_km_candidate.describe(),
}))
display(pd.DataFrame({
    'time_raw': measures.travel_time_raw.describe(),
    'time_min_candidate': measures.travel_time_min_candidate.describe(),
}))
daily = measures.groupby(['day_of_week', 'day']).agg(
    observations=('hour', 'size'),
    times_scaled=('time_scaled_candidate', 'sum'),
    distance_measurements_scaled=('distance_scaled_candidate', 'sum'),
    provided_tti_below_one=('source_tti_missing_or_below_one', 'sum'),
    provided_tti_above_five=('source_tti_above_five', 'sum'),
)
display(daily)
assert len(measures) == 7 * 440 * 24
assert (daily.observations == 440 * 24).all()
display(measures.loc[measures.time_scaled_candidate,
    ['sheet', '_excel_row', 'hour', 'travel_time_raw', 'travel_time_min_candidate']].head(10))"""),
        markdown("""## Clés des points et distances variables

Les indices source des trajets ne peuvent pas être joints directement à Table 0.
Un crosswalk est proposé à partir des coordonnées arrondies à 8 décimales, contrôlées
pour l'unicité. Tous les originaux restent disponibles. Les distances observées par jour
seront conservées même si dim_trajectory utilise la distance du lundi comme référence.
"""),
        code("""identifiers = report['identifiers']
display(pd.DataFrame([
    {'raw_index': int(raw), 'coordinate_point_index': values[0]}
    for raw, values in identifiers['point_index_crosswalk'].items()
    if len(values) == 1 and int(raw) != values[0]
]))
assert not identifiers['ambiguous_source_indices']
assert identifiers['unmatched_coordinates_measurements'] == 0
variants = routes.groupby(['origin_point_candidate', 'dest_point_candidate'])[
    'distance_km_candidate'].nunique()
display(variants.value_counts().sort_index().rename_axis('distance_variants').to_frame('trajectories'))
display(pd.Series(report['dimensions']).drop('points_per_commune'))"""),
        markdown("""## Recalcul indépendant du TTI et comparaison

Référence choisie : minimum des temps valides corrigés sur les **168 heures du même
trajet dirigé**. TTI candidat = temps / référence. Cette référence empirique ne prouve
pas un véritable état de circulation fluide et sera figée pour le rejeu horaire.
Le TTI fourni est conservé. Un écart absolu >0,1 déclenche un signal, sans suppression.
Le diagnostic temps/distance à 60 km/h est une comparaison, pas une formule affirmée
par la source. Un TTI élevé seul ne suffit pas à déclarer une mesure invalide.
"""),
        code("""display(measures[['tti_provided', 'tti_recalculated_candidate',
                  'tti_delta_candidate', 'speed_kmh_candidate']].describe())
hourly = measures.groupby('hour').agg(
    max_provided=('tti_provided', 'max'),
    max_recalculated=('tti_recalculated_candidate', 'max'),
    mean_absolute_gap=('tti_delta_candidate', lambda s: s.abs().mean()),
)
display(hourly)
sequence_present = np.allclose(hourly.loc[5:23, 'max_provided'], np.arange(5, 24))
print('Suite 5, 6, ..., 23 constatée :', sequence_present)
print('Écart absolu moyen :', measures.tti_delta_candidate.abs().mean())
print('Écarts >0,1 :', int(measures.tti_absolute_gap_above_0_1.sum()))
assert measures.tti_recalculated_candidate.ge(1).all()
route_keys = ['origin_point_candidate', 'dest_point_candidate']
assert measures[route_keys].drop_duplicates().shape[0] == 440"""),
        markdown("""## Conservation et limites

Aucune ligne n'a été supprimée et aucune table métier n'a encore été chargée.
Les règles seront implémentées et validées dans les phases 3–5 ; une mesure
irréparable devra rejoindre quarantine avec son motif. La densité source n'a pas
d'unité déclarée, les populations/ménages fractionnaires sont conservés.
Les outliers IQR ne sont pas des règles de rejet. Aucun lien causal n'est inféré.
"""),
        code("""final_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert final_hash == initial_hash == SOURCE_SHA256
assert len(report['sheets']) == 13
assert report['dimensions']['commune_count'] == 22
assert len(tables[0]) == 110
assert all(len(tables[n]) == 440 for n in range(5, 12))
print('Source intacte et cardinalités vérifiées. Notebook exécuté avec CasaTraffic.')"""),
    ]
    notebook = nbformat.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"display_name": "CasaTraffic (Python 3.11)",
                       "language": "python", "name": "casatraffic"},
        "language_info": {"name": "python", "version": "3.11.0"},
    })
    nbformat.write(notebook, ROOT / "notebooks/02_source_profiling.ipynb")
    print("Notebook de profilage créé.")


if __name__ == "__main__":
    main()
