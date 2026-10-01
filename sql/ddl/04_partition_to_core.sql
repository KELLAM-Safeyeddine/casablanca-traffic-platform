-- Exécuté dans la même transaction que le remplacement de la partition STAGING.
DELETE FROM public.fact_travel_time
WHERE day_of_week = %(day)s AND hour = ANY(%(hours)s);
INSERT INTO public.fact_travel_time (
    trajectory_id, day_of_week, hour, travel_time_min, tti, speed_kmh,
    distance_observed_km, free_flow_reference_min, tti_provided, tti_delta,
    tti_gap_flag, source_tti_flag, travel_time_raw, distance_raw,
    time_scaled, distance_scaled, index_repaired, origin_index_raw, dest_index_raw,
    source_sha256, source_file, sheet, excel_row
)
SELECT s.trajectory_id, s.day_of_week, s.hour, s.travel_time_min,
    s.travel_time_min / d.free_flow_reference_min,
    60 * s.distance_km / s.travel_time_min,
    s.distance_km, d.free_flow_reference_min, s.tti_provided,
    s.travel_time_min / d.free_flow_reference_min - s.tti_provided,
    abs(s.travel_time_min / d.free_flow_reference_min - s.tti_provided) > 0.1,
    s.tti_provided < 1 OR s.tti_provided > 5,
    s.travel_time_raw, s.distance_raw, s.time_scaled, s.distance_scaled,
    s.index_repaired, s.origin_index_raw, s.dest_index_raw,
    s.source_sha256, s.source_file, s.sheet, s.excel_row
FROM staging.travel_time AS s JOIN public.dim_trajectory AS d USING (trajectory_id)
WHERE s.source_sha256 = %(source_sha256)s
  AND s.day_of_week = %(day)s AND s.hour = ANY(%(hours)s);
