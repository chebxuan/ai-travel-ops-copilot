"""Save enquiries atomically through a restricted intake role, never owner credentials."""
import hashlib
import json
import uuid
import psycopg
from psycopg.types.json import Jsonb
from fastapi import HTTPException
from backend.app.storage.connection import intake_connection, settings
from backend.app.storage.repository import read_dataset, _snapshot
from backend.app.travel_schemas import TripPreviewResponse, CostEstimateRequest
from backend.app.services import enquiry_tokens, sales_pricing, travel_catalog
from backend.app.services.enquiry_notifications import enqueue


def receipt(row):
    return {'reference': row['reference'], 'status': 'received'}


def save_in_connection(conn, enquiry, signing_key):
    fingerprint = hashlib.sha256(json.dumps(enquiry.model_dump(mode='json', exclude={'request_id'}), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = conn.execute('SELECT reference,request_hash FROM journey_enquiries WHERE idempotency_key=%s', (enquiry.request_id,)).fetchone()
    if existing:
        if existing['request_hash'] != fingerprint:
            raise HTTPException(409, detail={'code': 'ENQUIRY_RETRY_CONFLICT'})
        return receipt(existing)
    preview = TripPreviewResponse.model_validate(enquiry_tokens.verify(enquiry.preview_token, 'preview', signing_key))
    product = preview.product
    allowed = {(route.day, route.choice) for route in product.quote_route_options}
    choices = [(route.day, route.choice) for route in enquiry.route_choices]
    if len(choices) != len(set(day for day, _ in choices)) or any(pair not in allowed for pair in choices):
        raise HTTPException(422, detail={'code': 'INVALID_ROUTE_CHOICE'})
    guide = next((option.code for option in product.quote_guide_options if option.code.endswith('-GUIDE-01')), None)
    trip = CostEstimateRequest(**{**preview.request.model_dump(), 'product_id': product.product_id,
        'is_peak': False, 'guide_code': guide if preview.request.need_guide else None,
        'route_choices': enquiry.route_choices})
    shown_quote = None
    if enquiry.quote_token:
        quoted = enquiry_tokens.verify(enquiry.quote_token, 'quote', signing_key)
        if quoted['request'] != trip.model_dump(mode='json'):
            raise HTTPException(422, detail={'code': 'QUOTE_JOURNEY_MISMATCH'})
        shown_quote = quoted['quote']
    data = read_dataset(conn)
    token = _snapshot.set(data)
    try:
        internal = None
        reason = None
        try:
            current = sales_pricing.quote(trip)
            if current['sales_quote']['status'] == 'estimated':
                internal = travel_catalog.estimate(trip)
            else: reason = current['sales_quote'].get('reason')
        except HTTPException as error:
            if error.status_code not in (404, 409, 422): raise
            reason = 'JOURNEY_REQUIRES_REVIEW'
            current = {'kind': 'traveller_sales_quote', 'product_id': product.product_id,
                'sales_quote': {'status': 'pending_confirmation', 'amount': None, 'currency': 'CNY', 'reason': reason}}
        changed = shown_quote is not None and shown_quote != current
        snapshot_id = None
        if internal is not None:
            snapshot_id = uuid.uuid4()
            codes = {line['code'] for line in internal['cost']['line_items']}
            versions = {code: data['price_versions'][code] for code in codes if code in data['price_versions']}
            conn.execute('INSERT INTO quote_snapshots(id,product_id,policy_id,request_data,internal_cost,public_quote,service_price_versions,actor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                (snapshot_id, product.product_id, data['configuration']['sales_policy']['id'], Jsonb(trip.model_dump(mode='json')), Jsonb(internal), Jsonb(current), Jsonb(versions), 'journey-enquiry'))
        id = uuid.uuid4()
        reference = 'TC-' + id.hex[:16].upper()
        conn.execute('INSERT INTO journey_enquiries(id,reference,idempotency_key,request_hash,name,email,message,product_id,preview_snapshot,shown_quote,verified_quote,quote_changed,quote_snapshot_id,review_reason,preferences) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (id, reference, enquiry.request_id, fingerprint, enquiry.name, enquiry.email, enquiry.message, product.product_id,
             Jsonb({'preview': preview.model_dump(mode='json', exclude={'preview_token'}), 'request': trip.model_dump(mode='json')}),
             Jsonb(shown_quote) if shown_quote is not None else None, Jsonb(current), changed, snapshot_id, reason, Jsonb({'hotel_preference': enquiry.hotel_preference, 'hotel_quote_status': 'not_included'})))
        enqueue(conn,id,reference,'product',product.product_id,changed or bool(reason))
        return receipt({'reference': reference})
    finally:
        _snapshot.reset(token)


def save_custom_in_connection(conn, enquiry):
    fingerprint = hashlib.sha256(json.dumps({'kind': 'custom', **enquiry.model_dump(mode='json', exclude={'request_id'})}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = conn.execute('SELECT reference,request_hash FROM journey_enquiries WHERE idempotency_key=%s', (enquiry.request_id,)).fetchone()
    if existing:
        if existing['request_hash'] != fingerprint:
            raise HTTPException(409, detail={'code': 'ENQUIRY_RETRY_CONFLICT'})
        return receipt(existing)
    preferences = enquiry.model_dump(mode='json', exclude={'request_id', 'name', 'email', 'message', 'website'})
    preferences['hotel_quote_status'] = 'not_included'
    id = uuid.uuid4()
    reference = 'TC-' + id.hex[:16].upper()
    conn.execute("INSERT INTO journey_enquiries(id,reference,idempotency_key,request_hash,name,email,message,product_id,enquiry_kind,preferences,preview_snapshot,verified_quote,quote_changed,review_reason) VALUES(%s,%s,%s,%s,%s,%s,%s,NULL,'custom',%s,%s,%s,false,'CUSTOM_JOURNEY_REQUIRES_REVIEW')",
        (id, reference, enquiry.request_id, fingerprint, enquiry.name, enquiry.email, enquiry.message,
         Jsonb(preferences), Jsonb({'preferences': preferences}), Jsonb({'status': 'pending_confirmation', 'amount': None, 'currency': 'CNY', 'reason': 'CUSTOM_JOURNEY_REQUIRES_REVIEW'})))
    enqueue(conn,id,reference,'custom',review=True)
    return receipt({'reference': reference})


def submit(enquiry, signing_key=None, *, custom=False):
    if settings()['source'] != 'postgres':
        raise HTTPException(503, detail={'code': 'ENQUIRY_UNAVAILABLE'})
    # Unique idempotency constraints handle simultaneous retries. A failed transaction
    # rolls back both the enquiry and quote before checking the winning transaction.
    for attempt in range(3):
        try:
            with intake_connection() as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                response = save_custom_in_connection(conn, enquiry) if custom else save_in_connection(conn, enquiry, signing_key)
            return response  # Only report received after COMMIT succeeds.
        except (psycopg.errors.UniqueViolation, psycopg.errors.SerializationFailure):
            if attempt == 2: break
        except (RuntimeError, psycopg.Error):
            break
    raise HTTPException(503, detail={'code': 'ENQUIRY_UNAVAILABLE'}) from None
