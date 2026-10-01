-- Semaine type unique : clés déterministes, pas de date d'observation inventée.
CREATE SCHEMA IF NOT EXISTS staging;
CREATE TABLE IF NOT EXISTS public.dim_commune (
    commune_id integer PRIMARY KEY,
    nom text NOT NULL,
    nom_key text NOT NULL,
    zip varchar(5) NOT NULL UNIQUE,
    population double precision NOT NULL CHECK (population >= 0 AND population < 'Infinity'),
    households double precision NOT NULL CHECK (households >= 0 AND households < 'Infinity'),
    density_source double precision NOT NULL CHECK (density_source >= 0 AND density_source < 'Infinity'),
    population_density_per_km2 double precision NOT NULL,
    tram_stations integer NOT NULL CHECK (tram_stations >= 0),
    bus_stations integer NOT NULL CHECK (bus_stations >= 0),
    primary_roads integer NOT NULL CHECK (primary_roads >= 0),
    secondary_roads integer NOT NULL CHECK (secondary_roads >= 0),
    highways integer NOT NULL CHECK (highways >= 0),
    region_area_m2 double precision NOT NULL CHECK (region_area_m2 > 0),
    parking_area_m2 double precision NOT NULL CHECK (parking_area_m2 >= 0),
    industrial_area_m2 double precision NOT NULL CHECK (industrial_area_m2 >= 0),
    parks_area_m2 double precision NOT NULL CHECK (parks_area_m2 >= 0),
    residential_area_m2 double precision NOT NULL CHECK (residential_area_m2 >= 0),
    university_area_m2 double precision NOT NULL CHECK (university_area_m2 >= 0),
    commercial_buildings integer NOT NULL CHECK (commercial_buildings >= 0),
    UNIQUE (nom_key, zip)
);
CREATE TABLE IF NOT EXISTS public.dim_point (
    point_id integer PRIMARY KEY CHECK (point_id BETWEEN 0 AND 109),
    commune_id integer NOT NULL REFERENCES public.dim_commune,
    lat double precision NOT NULL CHECK (lat BETWEEN 33.3 AND 33.8),
    lon double precision NOT NULL CHECK (lon BETWEEN -7.9 AND -7.2),
    geom geometry(Point, 4326) GENERATED ALWAYS AS
        (ST_SetSRID(ST_MakePoint(lon, lat), 4326)) STORED,
    UNIQUE (lat, lon)
);
CREATE INDEX IF NOT EXISTS dim_point_geom_idx ON public.dim_point USING gist (geom);
CREATE TABLE IF NOT EXISTS public.dim_time (
    day_of_week smallint NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    hour smallint NOT NULL CHECK (hour BETWEEN 0 AND 23),
    is_weekend boolean NOT NULL,
    period text NOT NULL CHECK (period IN ('morning_peak', 'evening_peak', 'off_peak', 'night')),
    PRIMARY KEY (day_of_week, hour)
);
CREATE TABLE IF NOT EXISTS public.dim_trajectory (
    trajectory_id integer PRIMARY KEY,
    origin_point_id integer NOT NULL REFERENCES public.dim_point,
    dest_point_id integer NOT NULL REFERENCES public.dim_point,
    distance_km double precision NOT NULL CHECK (distance_km > 0 AND distance_km < 'Infinity'),
    free_flow_reference_min double precision NOT NULL
        CHECK (free_flow_reference_min > 0 AND free_flow_reference_min < 'Infinity'),
    reference_source_sha256 text NOT NULL,
    UNIQUE (origin_point_id, dest_point_id),
    CHECK (origin_point_id <> dest_point_id)
);
CREATE TABLE IF NOT EXISTS staging.commune (
    LIKE public.dim_commune INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
);
CREATE TABLE IF NOT EXISTS staging.point (
    point_id integer PRIMARY KEY, commune_id integer NOT NULL,
    lat double precision NOT NULL, lon double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS staging.trajectory (
    LIKE public.dim_trajectory INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
);
CREATE TABLE IF NOT EXISTS staging.travel_time (
    source_sha256 text NOT NULL,
    trajectory_id integer NOT NULL REFERENCES public.dim_trajectory,
    day_of_week smallint NOT NULL,
    hour smallint NOT NULL,
    travel_time_min double precision NOT NULL CHECK (travel_time_min > 0 AND travel_time_min < 'Infinity'),
    distance_km double precision NOT NULL CHECK (distance_km > 0 AND distance_km < 'Infinity'),
    travel_time_raw double precision NOT NULL,
    distance_raw double precision NOT NULL,
    tti_provided double precision NOT NULL CHECK (tti_provided > 0 AND tti_provided < 'Infinity'),
    time_scaled boolean NOT NULL,
    distance_scaled boolean NOT NULL,
    index_repaired boolean NOT NULL,
    origin_index_raw integer NOT NULL,
    dest_index_raw integer NOT NULL,
    source_file text NOT NULL,
    sheet text NOT NULL,
    excel_row integer NOT NULL,
    PRIMARY KEY (source_sha256, trajectory_id, day_of_week, hour),
    FOREIGN KEY (day_of_week, hour) REFERENCES public.dim_time
);
CREATE TABLE IF NOT EXISTS public.fact_travel_time (
    trajectory_id integer NOT NULL REFERENCES public.dim_trajectory,
    day_of_week smallint NOT NULL,
    hour smallint NOT NULL,
    travel_time_min double precision NOT NULL CHECK (travel_time_min > 0 AND travel_time_min < 'Infinity'),
    tti double precision NOT NULL CHECK (tti >= 1 AND tti < 'Infinity'),
    speed_kmh double precision NOT NULL CHECK (speed_kmh > 0 AND speed_kmh < 'Infinity'),
    distance_observed_km double precision NOT NULL,
    free_flow_reference_min double precision NOT NULL,
    tti_provided double precision NOT NULL,
    tti_delta double precision NOT NULL,
    tti_gap_flag boolean NOT NULL,
    source_tti_flag boolean NOT NULL,
    travel_time_raw double precision NOT NULL,
    distance_raw double precision NOT NULL,
    time_scaled boolean NOT NULL,
    distance_scaled boolean NOT NULL,
    index_repaired boolean NOT NULL,
    origin_index_raw integer NOT NULL,
    dest_index_raw integer NOT NULL,
    source_sha256 text NOT NULL,
    source_file text NOT NULL,
    sheet text NOT NULL,
    excel_row integer NOT NULL,
    PRIMARY KEY (trajectory_id, day_of_week, hour),
    FOREIGN KEY (day_of_week, hour) REFERENCES public.dim_time
);
CREATE INDEX IF NOT EXISTS fact_travel_time_day_hour_idx
    ON public.fact_travel_time (day_of_week, hour);

-- Le rôle est créé au premier init Docker ; absent dans les tests SQL isolés.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'traffic_dashboard') THEN
        GRANT SELECT ON public.dim_commune, public.dim_point, public.dim_trajectory,
            public.fact_travel_time TO traffic_dashboard;
    END IF;
END $$;
