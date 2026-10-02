SELECT f.*, p.point_id, p.commune_id, c.nom commune,
       ST_Y(p.geom) latitude, ST_X(p.geom) longitude,
       c.population_density_per_km2, c.tram_stations, c.primary_roads
FROM public.fact_travel_time f
JOIN public.dim_trajectory t USING (trajectory_id)
JOIN public.dim_point p ON p.point_id=t.origin_point_id
JOIN public.mart_commune_features c ON c.commune_id=p.commune_id
WHERE p.commune_id=ANY(%(communes)s) AND f.day_of_week=ANY(%(days)s)
  AND f.hour BETWEEN %(start)s AND %(end)s
