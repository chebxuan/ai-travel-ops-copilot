CREATE TABLE journey_enquiries (
    id uuid PRIMARY KEY,
    reference text NOT NULL UNIQUE,
    idempotency_key uuid NOT NULL UNIQUE,
    request_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    name text NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
    email text NOT NULL CHECK(length(email) BETWEEN 3 AND 254),
    message text NOT NULL DEFAULT '',
    product_id text NOT NULL REFERENCES products(id),
    source text NOT NULL DEFAULT '/plan',
    status text NOT NULL DEFAULT 'new' CHECK(status IN ('new','following_up','proposal_sent','confirmed','closed')),
    preview_snapshot jsonb NOT NULL,
    shown_quote jsonb,
    verified_quote jsonb NOT NULL,
    quote_changed boolean NOT NULL,
    quote_snapshot_id uuid REFERENCES quote_snapshots(id),
    review_reason text
);
CREATE INDEX journey_enquiries_created ON journey_enquiries(created_at DESC);
REVOKE ALL ON journey_enquiries FROM travel_app;
