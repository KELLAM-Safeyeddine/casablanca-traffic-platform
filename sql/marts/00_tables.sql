-- Tables analytiques persistantes, reconstruites ensemble dans une transaction.
CREATE TABLE IF NOT EXISTS public.mart_commune_hourly_congestion (
    commune_id integer NOT NULL REFERENCES public.dim_commune,
    day_of_week smallint NOT NULL,
    hour smallint NOT NULL,
    measurement_count integer NOT NULL CHECK (measurement_count > 0),
    tti_mean double precision NOT NULL CHECK (tti_mean >= 1),
    tti_p95 double precision NOT NULL CHECK (tti_p95 >= 1),
    speed_mean_kmh double precision NOT NULL CHECK (speed_mean_kmh > 0),
    tti_gap_count integer NOT NULL CHECK (tti_gap_count BETWEEN 0 AND measurement_count),
    PRIMARY KEY (commune_id, day_of_week, hour),
    FOREIGN KEY (day_of_week, hour) REFERENCES public.dim_time
);
CREATE TABLE IF NOT EXISTS public.mart_peak_hours (
    commune_id integer NOT NULL REFERENCES public.dim_commune,
    day_of_week smallint NOT NULL,
    hour smallint NOT NULL,
    tti_mean double precision NOT NULL,
    tti_p95 double precision NOT NULL,
    measurement_count integer NOT NULL,
    PRIMARY KEY (commune_id, day_of_week, hour),
    FOREIGN KEY (day_of_week, hour) REFERENCES public.dim_time
);
CREATE TABLE IF NOT EXISTS public.mart_weekday_vs_weekend (
    commune_id integer NOT NULL REFERENCES public.dim_commune,
    is_weekend boolean NOT NULL,
    day_count integer NOT NULL CHECK (day_count > 0),
    measurement_count integer NOT NULL CHECK (measurement_count > 0),
    tti_mean double precision NOT NULL CHECK (tti_mean >= 1),
    tti_p95 double precision NOT NULL CHECK (tti_p95 >= 1),
    speed_mean_kmh double precision NOT NULL CHECK (speed_mean_kmh > 0),
    PRIMARY KEY (commune_id, is_weekend)
);
CREATE TABLE IF NOT EXISTS public.mart_commune_features (
    LIKE public.dim_commune INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
);
ALTER TABLE public.mart_commune_features
    ADD COLUMN IF NOT EXISTS measurement_count integer NOT NULL,
    ADD COLUMN IF NOT EXISTS tti_mean double precision NOT NULL,
    ADD COLUMN IF NOT EXISTS tti_p95 double precision NOT NULL,
    ADD COLUMN IF NOT EXISTS speed_mean_kmh double precision NOT NULL,
    ADD COLUMN IF NOT EXISTS tti_gap_count integer NOT NULL;

-- Donner accès aux marts sur un volume neuf, après création des quatre tables.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'traffic_dashboard') THEN
        GRANT SELECT ON public.mart_commune_hourly_congestion, public.mart_peak_hours,
            public.mart_weekday_vs_weekend, public.mart_commune_features TO traffic_dashboard;
    END IF;
END $$;
