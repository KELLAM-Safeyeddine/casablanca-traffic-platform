DELETE FROM public.mart_commune_features;
INSERT INTO public.mart_commune_features
SELECT c.*, a.measurement_count, a.tti_mean, a.tti_p95, a.speed_mean_kmh, a.tti_gap_count
FROM public.dim_commune c
JOIN (
    SELECT p.commune_id, count(*)::integer AS measurement_count,
        avg(f.tti ORDER BY f.trajectory_id, f.day_of_week, f.hour) AS tti_mean,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY f.tti) AS tti_p95,
        avg(f.speed_kmh ORDER BY f.trajectory_id, f.day_of_week, f.hour) AS speed_mean_kmh,
        count(*) FILTER (WHERE f.tti_gap_flag)::integer AS tti_gap_count
    FROM public.fact_travel_time f
    JOIN public.dim_trajectory t USING (trajectory_id)
    JOIN public.dim_point p ON p.point_id = t.origin_point_id
    GROUP BY p.commune_id
) a USING (commune_id);
