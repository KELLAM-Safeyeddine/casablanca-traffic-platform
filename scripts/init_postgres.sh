#!/usr/bin/env bash
# Initialise les bases applicatives au premier démarrage du volume PostgreSQL.
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 \
    --set airflow_password="$AIRFLOW_DB_PASSWORD" \
    --set traffic_password="$TRAFFIC_DB_PASSWORD" \
    --set metabase_password="$METABASE_DB_PASSWORD" \
    --file /opt/bootstrap/00_platform.sql
