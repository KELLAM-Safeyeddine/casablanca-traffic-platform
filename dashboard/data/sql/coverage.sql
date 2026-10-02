SELECT (SELECT count(*) FROM public.fact_travel_time) facts,
       (SELECT count(*) FROM public.dim_point) points,
       (SELECT count(*) FROM public.dim_trajectory) trajectories,
       (SELECT count(*) FROM public.mart_commune_features) communes;
