"""Operations API: separate short-lived service assertions, never the public API key."""
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from typing import Literal
import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from backend.app.storage.connection import restricted_connection, settings

REFERENCE = re.compile(r'^TC-[A-F0-9]{16}$')


async def operator(request: Request, x_ops_assertion: str = Header(default='')):
    key = os.getenv('OPS_BACKEND_KEY','')
    if len(key) < 32 or key == os.getenv('API_KEY'):
        raise HTTPException(503, detail={'code':'OPS_UNAVAILABLE'})
    try:
        if len(x_ops_assertion)>2048:
            raise ValueError()
        encoded, signature = x_ops_assertion.split('.')
        expected = hmac.new(key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,signature):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))
        now = time.time()
        if (not 0 < data['exp']-now <= 65 or data['method'] != request.method
            or data['path'] != request.url.path or data['query'] != request.url.query
            or data['body'] != hashlib.sha256(await request.body()).hexdigest()
            or not re.fullmatch(r'[A-Za-z0-9_.@-]{1,80}',data['actor'])):
            raise ValueError()
        return data['actor']
    except (ValueError,KeyError,TypeError,binascii.Error):
        raise HTTPException(401,detail={'code':'OPS_UNAUTHORIZED'}) from None


def validate_reference(reference):
    if not REFERENCE.fullmatch(reference):
        raise HTTPException(404,detail={'code':'ENQUIRY_NOT_FOUND'})


def storage_call(function):
    if settings()['source'] != 'postgres':
        raise HTTPException(503, detail={'code':'OPS_UNAVAILABLE'})
    try:
        with restricted_connection('ops') as conn:
            return function(conn)
    except (RuntimeError,psycopg.Error):
        raise HTTPException(503, detail={'code':'OPS_UNAVAILABLE'}) from None


class StatusChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['new','following_up','proposal_sent','closed']
    expected_version: int = Field(ge=1)


def change_status(conn,reference,change,actor):
    row=conn.execute('SELECT id,status,status_version FROM journey_enquiries WHERE reference=%s FOR UPDATE',(reference,)).fetchone()
    if not row:
        raise HTTPException(404,detail={'code':'ENQUIRY_NOT_FOUND'})
    if row['status_version'] != change.expected_version:
        raise HTTPException(409,detail={'code':'STATUS_CONFLICT'})
    if row['status']==change.status:
        return {'status':row['status'],'status_version':row['status_version']}
    version=row['status_version']+1
    conn.execute('UPDATE journey_enquiries SET status=%s,status_version=%s,updated_at=now() WHERE id=%s',(change.status,version,row['id']))
    conn.execute('INSERT INTO enquiry_status_events(id,enquiry_id,actor,old_status,new_status,status_version) VALUES(%s,%s,%s,%s,%s,%s)',(uuid.uuid4(),row['id'],actor,row['status'],change.status,version))
    return {'status':change.status,'status_version':version}


router = APIRouter(prefix='/api/ops',tags=['Operations'],dependencies=[Depends(operator)])


@router.get('/enquiries')
def enquiries(status: Literal['new','following_up','proposal_sent','confirmed','closed'] | None = None,
              page: int = Query(default=1,ge=1,le=100000), limit: int=Query(default=20,ge=1,le=50)):
    def query(conn):
        where = ' WHERE status=%s' if status else ''
        params = (status,) if status else ()
        total = conn.execute('SELECT count(*) AS n FROM journey_enquiries'+where,params).fetchone()['n']
        rows = conn.execute('SELECT reference,created_at,enquiry_kind,product_id,name,status,status_version,quote_changed,review_reason FROM journey_enquiries'+where+' ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s',params+(limit,(page-1)*limit)).fetchall()
        return {'items':rows,'total':total,'page':page,'limit':limit}
    return storage_call(query)


@router.get('/enquiries/{reference}')
def enquiry(reference: str):
    validate_reference(reference)
    def query(conn):
        # Explicit projection: no request hash, signed token or internal quote snapshot.
        row = conn.execute('SELECT id,reference,created_at,updated_at,name,email,message,product_id,enquiry_kind,preferences,status,status_version,preview_snapshot,shown_quote,verified_quote,quote_changed,review_reason FROM journey_enquiries WHERE reference=%s',(reference,)).fetchone()
        if not row:
            raise HTTPException(404,detail={'code':'ENQUIRY_NOT_FOUND'})
        events=conn.execute('SELECT created_at,actor,old_status,new_status,status_version FROM enquiry_status_events WHERE enquiry_id=%s ORDER BY status_version',(row['id'],)).fetchall()
        notifications=conn.execute('SELECT state,attempts,sent_at,last_error FROM enquiry_notifications WHERE enquiry_id=%s',(row['id'],)).fetchall()
        row.pop('id')
        return {**row,'events':events,'notifications':notifications}
    return storage_call(query)


@router.post('/enquiries/{reference}/status')
def update_status(reference: str,change: StatusChange,actor: str=Depends(operator)):
    validate_reference(reference)
    return storage_call(lambda conn: change_status(conn,reference,change,actor))
