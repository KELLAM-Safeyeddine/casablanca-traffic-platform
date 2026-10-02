count(*)::integer measurement_count, avg(tti) tti_mean,
percentile_cont(0.95) WITHIN GROUP (ORDER BY tti) tti_p95,
avg(speed_kmh) speed_mean_kmh, avg(travel_time_min) travel_mean_min,
count(*) FILTER (WHERE tti_gap_flag)::integer tti_gap_count
