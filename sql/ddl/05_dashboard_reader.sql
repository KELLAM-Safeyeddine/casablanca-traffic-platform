-- Rôle créé par 00_platform.sql avec secret .env ; migration réversible des droits.
ALTER ROLE traffic_dashboard SET default_transaction_read_only = on;
GRANT CONNECT ON DATABASE traffic TO traffic_dashboard;
GRANT USAGE ON SCHEMA public TO traffic_dashboard;
GRANT SELECT ON public.dim_commune, public.dim_point, public.dim_trajectory,
    public.fact_travel_time, public.mart_commune_hourly_congestion,
    public.mart_peak_hours, public.mart_weekday_vs_weekend,
    public.mart_commune_features TO traffic_dashboard;
