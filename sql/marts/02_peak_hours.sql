DELETE FROM public.mart_peak_hours;
INSERT INTO public.mart_peak_hours
SELECT commune_id, day_of_week, hour, tti_mean, tti_p95, measurement_count
FROM (
    SELECT h.*, dense_rank() OVER (
        PARTITION BY commune_id, day_of_week ORDER BY tti_mean DESC
    ) AS peak_rank
    FROM public.mart_commune_hourly_congestion h
) ranked
WHERE peak_rank = 1;
