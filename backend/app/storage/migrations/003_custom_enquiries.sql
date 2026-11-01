-- Preserve existing product enquiries while accepting enquiries without a selected product.
ALTER TABLE journey_enquiries ALTER COLUMN product_id DROP NOT NULL;
ALTER TABLE journey_enquiries ADD COLUMN enquiry_kind text NOT NULL DEFAULT 'product'
    CHECK (enquiry_kind IN ('product', 'custom'));
ALTER TABLE journey_enquiries ADD COLUMN preferences jsonb NOT NULL DEFAULT '{}';
ALTER TABLE journey_enquiries ADD CONSTRAINT journey_enquiry_product_kind
    CHECK ((enquiry_kind = 'product' AND product_id IS NOT NULL)
        OR (enquiry_kind = 'custom' AND product_id IS NULL AND quote_snapshot_id IS NULL AND shown_quote IS NULL));
