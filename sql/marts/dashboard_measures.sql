-- Lecture des faits : coordonnées PostGIS, grain trajet/jour/heure sans agrégation préalable.
SELECT f.trajectory_id, f.day_of_week, f.hour, f.tti, f.speed_kmh,
       p.point_id, c.commune_id, c.nom commune,
       ST_Y(p.geom) latitude, ST_X(p.geom) longitude
FROM public.fact_travel_time f
JOIN public.dim_trajectory t USING (trajectory_id)
JOIN public.dim_point p ON p.point_id = t.origin_point_id
JOIN public.dim_commune c USING (commune_id)
ORDER BY f.trajectory_id, f.day_of_week, f.hour;
