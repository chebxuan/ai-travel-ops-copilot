"""Transactional outbox. Only the independent worker makes outbound requests."""
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import time
import uuid
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from psycopg.types.json import Jsonb
from backend.app.storage.connection import restricted_connection

MAX_ATTEMPTS = 8


def enqueue(conn, enquiry_id, reference, kind, product_id=None, review=False):
    # No contact details, customer prose, internal costs or supplier information.
    payload = {'reference': reference, 'kind': kind, 'product_id': product_id,
               'received_at': datetime.now(timezone.utc).isoformat(), 'review': bool(review)}
    conn.execute('INSERT INTO enquiry_notifications(id,enquiry_id,payload) VALUES(%s,%s,%s)',
                 (uuid.uuid4(), enquiry_id, Jsonb(payload)))


def configuration():
    if os.getenv('FEISHU_NOTIFICATIONS_ENABLED') != '1':
        raise ValueError('Notifications disabled')
    url = os.getenv('FEISHU_WEBHOOK_URL','')
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'open.feishu.cn'
            or not parsed.path.startswith('/open-apis/bot/v2/hook/')
            or not parsed.path.removeprefix('/open-apis/bot/v2/hook/')
            or parsed.query or parsed.fragment):
        raise ValueError('Invalid Feishu webhook')
    secret = os.getenv('FEISHU_SIGNING_SECRET','')
    origin = os.getenv('OPS_SITE_ORIGIN','')
    site = urlsplit(origin)
    if not secret or site.scheme != 'https' or not site.netloc or site.username or site.password or site.path not in ('','/') or site.query or site.fragment:
        raise ValueError('Signing secret and HTTPS operations origin required')
    return url, secret, origin.rstrip('/')


def message(payload, secret, origin, timestamp=None):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    # Feishu algorithm: timestamp + newline + secret is the HMAC key, empty message.
    signature = base64.b64encode(hmac.new((timestamp+'\n'+secret).encode(), b'', hashlib.sha256).digest()).decode()
    reference = payload['reference']
    text = ('Travel Copilot 新咨询\n编号：'+reference+'\n类型：'+
            ('产品咨询' if payload['kind']=='product' else '独立需求')+
            '\n产品：'+(payload.get('product_id') or '未指定')+
            '\n收到时间：'+payload['received_at']+
            '\n需复核：'+('是' if payload['review'] else '按常规流程跟进')+
            '\n查看：'+origin+'/ops?reference='+reference+
            '\n咨询已保存，不代表预订确认。')
    return {'timestamp': timestamp, 'sign': signature, 'msg_type':'text', 'content':{'text':text}}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def deliver(payload, config):
    url, secret, origin = config
    data = json.dumps(message(payload,secret,origin),ensure_ascii=False).encode()
    request = Request(url,data=data,headers={'Content-Type':'application/json'},method='POST')
    with build_opener(NoRedirect()).open(request,timeout=10) as response:
        result = json.loads(response.read(32768))
    if result.get('code', result.get('StatusCode')) != 0:
        # Do not log bot error text: it can echo user data or the webhook.
        raise RuntimeError('Feishu rejected notification')


def claim(conn):
    conn.execute("UPDATE enquiry_notifications SET state='failed',lease_id=NULL,lease_until=NULL,last_error='LEASE_EXHAUSTED' WHERE state='sending' AND lease_until<now() AND attempts>=8")
    job = conn.execute("SELECT id,payload,attempts FROM enquiry_notifications WHERE attempts<8 AND ((state='pending' AND available_at<=now()) OR (state='sending' AND lease_until<now())) ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
    if not job:
        return None
    lease = uuid.uuid4()
    conn.execute("UPDATE enquiry_notifications SET state='sending',attempts=attempts+1,lease_id=%s,lease_until=now()+interval '5 minutes' WHERE id=%s",(lease,job['id']))
    return {**job,'lease_id':lease,'attempts':job['attempts']+1}


def finish(conn, job, success):
    # A stale process cannot acknowledge a lease already reclaimed by another worker.
    if success:
        conn.execute("UPDATE enquiry_notifications SET state='sent',sent_at=now(),lease_id=NULL,lease_until=NULL,last_error=NULL WHERE id=%s AND state='sending' AND lease_id=%s",(job['id'],job['lease_id']))
    else:
        state = 'failed' if job['attempts'] >= MAX_ATTEMPTS else 'pending'
        delay = min(3600,60 * 2**(job['attempts']-1))
        conn.execute("UPDATE enquiry_notifications SET state=%s,available_at=now()+%s*interval '1 second',lease_id=NULL,lease_until=NULL,last_error='DELIVERY_FAILED' WHERE id=%s AND state='sending' AND lease_id=%s",(state,delay,job['id'],job['lease_id']))


def process_one(config):
    with restricted_connection('notification') as conn:
        job = claim(conn)
    if not job:
        return False
    try:
        deliver(job['payload'],config)
        success = True
    except Exception:
        success = False
    with restricted_connection('notification') as conn:
        finish(conn,job,success)
    print('Notification',str(job['id']), 'sent' if success else 'retry/failed',flush=True)
    return True


def run():
    config = configuration()  # Fail before claiming any work if configuration is missing.
    while True:
        try:
            worked = process_one(config)
        except Exception:
            print('Notification worker storage unavailable',flush=True)
            worked = False
        time.sleep(2 if worked else 10)  # Single worker, <=30 messages/minute.


if __name__ == '__main__':
    from dotenv import load_dotenv
    from backend.app.core.paths import ROOT
    load_dotenv(ROOT / '.env')
    try:
        run()
    except (ValueError, RuntimeError):
        raise SystemExit('Notification configuration unavailable; check operations guide.') from None
