-- Journal persistant des rejets, anomalies réparables et avertissements source.
CREATE TABLE IF NOT EXISTS public.quarantine (
    event_id text PRIMARY KEY,
    source_sha256 text NOT NULL CHECK (length(source_sha256) = 64),
    source_file text NOT NULL,
    sheet text NOT NULL,
    excel_row integer NOT NULL CHECK (excel_row > 0),
    hour smallint NOT NULL CHECK (hour BETWEEN -1 AND 23),
    column_name text NOT NULL,
    reason text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('rejected', 'repairable', 'warning')),
    raw_payload jsonb NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    last_run_id text NOT NULL
);
CREATE INDEX IF NOT EXISTS quarantine_source_severity_idx
    ON public.quarantine (source_sha256, severity);
