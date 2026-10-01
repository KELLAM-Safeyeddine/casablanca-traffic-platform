INSERT INTO public.dim_commune SELECT * FROM staging.commune
ON CONFLICT (commune_id) DO NOTHING;
INSERT INTO public.dim_point (point_id, commune_id, lat, lon)
SELECT point_id, commune_id, lat, lon FROM staging.point
ON CONFLICT (point_id) DO NOTHING;
INSERT INTO public.dim_time (day_of_week, hour, is_weekend, period)
SELECT day, hour, day IN (6, 7),
    CASE WHEN hour BETWEEN 7 AND 9 THEN 'morning_peak'
         WHEN hour BETWEEN 17 AND 19 THEN 'evening_peak'
         WHEN hour < 6 OR hour >= 22 THEN 'night'
         ELSE 'off_peak' END
FROM generate_series(1, 7) AS day CROSS JOIN generate_series(0, 23) AS hour
ON CONFLICT (day_of_week, hour) DO NOTHING;
INSERT INTO public.dim_trajectory SELECT * FROM staging.trajectory
ON CONFLICT (trajectory_id) DO NOTHING;
