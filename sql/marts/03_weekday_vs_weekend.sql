DELETE FROM public.mart_weekday_vs_weekend;
INSERT INTO public.mart_weekday_vs_weekend
SELECT p.commune_id, d.is_weekend, count(DISTINCT f.day_of_week)::integer, count(*)::integer,
    avg(f.tti ORDER BY f.trajectory_id, f.day_of_week, f.hour),
    percentile_cont(0.95) WITHIN GROUP (ORDER BY f.tti),
    avg(f.speed_kmh ORDER BY f.trajectory_id, f.day_of_week, f.hour)
FROM public.fact_travel_time f
JOIN public.dim_time d USING (day_of_week, hour)
JOIN public.dim_trajectory t USING (trajectory_id)
JOIN public.dim_point p ON p.point_id = t.origin_point_id
GROUP BY p.commune_id, d.is_weekend;
