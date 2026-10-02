"""Pool PostgreSQL concurrent, exclusivement en lecture seule."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st
from psycopg2.extensions import connection
from psycopg2.pool import ThreadedConnectionPool


@st.cache_resource
def pool() -> ThreadedConnectionPool:
    """Réutiliser un pool borné, pas une transaction partagée entre utilisateurs."""
    return ThreadedConnectionPool(
        1,
        8,
        host=os.environ["DASHBOARD_DB_HOST"],
        port=os.environ.get("DASHBOARD_DB_PORT", "5432"),
        dbname=os.environ.get("DASHBOARD_DB_NAME", "traffic"),
        user=os.environ.get("DASHBOARD_DB_USER", "traffic_dashboard"),
        password=os.environ["DASHBOARD_DB_PASSWORD"],
        connect_timeout=3,
        options="-c default_transaction_read_only=on -c statement_timeout=5000",
    )


@contextmanager
def reading() -> Iterator[connection]:
    """Fermer la transaction et remettre seulement une connexion saine dans le pool."""
    shared = pool()
    database = shared.getconn()
    try:
        database.set_session(readonly=True, autocommit=False)
        yield database
    finally:
        if not database.closed:
            database.rollback()
        shared.putconn(database, close=bool(database.closed))
