-- Additive only: preserve enquiry contact data and all original quote snapshots.
ALTER TABLE journey_enquiries ADD COLUMN status_version integer NOT NULL DEFAULT 1 CHECK(status_version > 0);
ALTER TABLE journey_enquiries ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
CREATE TABLE enquiry_status_events (
    id uuid PRIMARY KEY,
    enquiry_id uuid NOT NULL REFERENCES journey_enquiries(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    actor text NOT NULL,
    old_status text NOT NULL,
    new_status text NOT NULL,
    status_version integer NOT NULL,
    UNIQUE(enquiry_id,status_version)
);
CREATE TABLE enquiry_notifications (
    id uuid PRIMARY KEY,
    enquiry_id uuid NOT NULL REFERENCES journey_enquiries(id),
    channel text NOT NULL DEFAULT 'feishu' CHECK(channel='feishu'),
    payload jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','sending','sent','failed')),
    attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 8),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_id uuid,
    lease_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    last_error text,
    UNIQUE(enquiry_id,channel)
);
CREATE INDEX enquiry_notifications_due ON enquiry_notifications(state,available_at);
CREATE INDEX journey_enquiries_ops_list ON journey_enquiries(status,created_at DESC,id DESC);
REVOKE ALL ON enquiry_status_events,enquiry_notifications FROM PUBLIC;
