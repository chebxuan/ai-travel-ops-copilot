"""Signed public snapshots: no costs or connection credentials enter these tokens."""
import base64
import hashlib
import hmac
import json
import time
from fastapi import HTTPException

MAX_AGE = 7200


def issue(kind, data, key):
    raw = json.dumps({'v': 1, 'kind': kind, 'issued_at': int(time.time()), 'data': data}, ensure_ascii=False, separators=(',', ':')).encode()
    encoded = base64.urlsafe_b64encode(raw).decode().rstrip('=')
    signature = hmac.new(key.encode(), ('travel-enquiry:v1:' + encoded).encode(), hashlib.sha256).hexdigest()
    return encoded + '.' + signature


def verify(token, kind, key):
    try:
        encoded, signature = token.rsplit('.', 1)
        expected = hmac.new(key.encode(), ('travel-enquiry:v1:' + encoded).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected): raise ValueError()
        envelope = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        if envelope['v'] != 1 or envelope['kind'] != kind: raise ValueError()
        age = time.time() - envelope['issued_at']
        if age > MAX_AGE:
            raise HTTPException(409, detail={'code': 'PREVIEW_EXPIRED'})
        if age < -30: raise ValueError()
        return envelope['data']
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, detail={'code': 'INVALID_JOURNEY_SNAPSHOT'}) from None
