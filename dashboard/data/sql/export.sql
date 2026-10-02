SELECT commune, point_id, trajectory_id, day_of_week, hour,
       tti, speed_kmh, travel_time_min, tti_provided, tti_delta,
       distance_observed_km, time_scaled, distance_scaled, index_repaired
FROM selected ORDER BY commune, day_of_week, hour, trajectory_id
