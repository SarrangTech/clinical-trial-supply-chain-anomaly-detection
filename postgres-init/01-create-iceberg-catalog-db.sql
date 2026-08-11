-- The single Postgres container in docker-compose.yml serves two independent
-- roles: the Airflow metadata database (created automatically by the
-- POSTGRES_DB env var) and the JDBC backend for the Iceberg REST catalog
-- (tabulario/iceberg-rest). They are kept in separate databases -- not
-- separate schemas of the same database -- so the Iceberg catalog's tables
-- (which the REST catalog service manages itself) can never collide with or
-- be mistaken for Airflow's own metadata tables.
CREATE DATABASE iceberg_catalog;
