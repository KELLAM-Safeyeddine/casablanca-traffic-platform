-- Infrastructure seulement. Le modèle STAGING/CORE sera ajouté en phase 5.
CREATE ROLE airflow LOGIN PASSWORD :'airflow_password';
CREATE ROLE traffic LOGIN PASSWORD :'traffic_password';
CREATE ROLE metabase LOGIN PASSWORD :'metabase_password';
CREATE ROLE traffic_dashboard LOGIN PASSWORD :'dashboard_password';
CREATE DATABASE airflow OWNER airflow;
CREATE DATABASE traffic OWNER traffic;
CREATE DATABASE metabase OWNER metabase;
REVOKE CONNECT ON DATABASE airflow FROM PUBLIC;
REVOKE CONNECT ON DATABASE traffic FROM PUBLIC;
REVOKE CONNECT ON DATABASE metabase FROM PUBLIC;
GRANT CONNECT ON DATABASE airflow TO airflow;
GRANT CONNECT ON DATABASE traffic TO traffic;
GRANT CONNECT ON DATABASE traffic TO traffic_dashboard;
GRANT CONNECT ON DATABASE metabase TO metabase;
\connect traffic
CREATE EXTENSION IF NOT EXISTS postgis;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO traffic;
GRANT USAGE ON SCHEMA public TO traffic_dashboard;
\connect airflow
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO airflow;
\connect metabase
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO metabase;
