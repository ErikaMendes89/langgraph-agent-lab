-- Executado apenas na criação de um volume vazio, pelo administrador local.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE incident_lab LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
SELECT format('ALTER ROLE incident_lab PASSWORD %L',
              trim(pg_read_file('/run/secrets/app_password'))) \gexec
GRANT CONNECT ON DATABASE incident_lab TO incident_lab;
GRANT USAGE, CREATE ON SCHEMA public TO incident_lab;
