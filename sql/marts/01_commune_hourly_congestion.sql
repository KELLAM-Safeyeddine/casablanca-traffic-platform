DELETE FROM public.mart_commune_hourly_congestion;
INSERT INTO public.mart_commune_hourly_congestion
SELECT p.commune_id, f.day_of_week, f.hour, count(*)::integer,
    avg(f.tti ORDER BY f.trajectory_id),
    percentile_cont(0.95) WITHIN GROUP (ORDER BY f.tti),
    avg(f.speed_kmh ORDER BY f.trajectory_id),
    count(*) FILTER (WHERE f.tti_gap_flag)::integer
FROM public.fact_travel_time f
JOIN public.dim_trajectory t USING (trajectory_id)
JOIN public.dim_point p ON p.point_id = t.origin_point_id
GROUP BY p.commune_id, f.day_of_week, f.hour;
