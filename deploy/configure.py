"""Create server-specific credentials once, without displaying their values."""
import argparse
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', required=True, help='http://server-IP for testing, or your domain for HTTPS')
    parser.add_argument('--http-port', type=int, default=80)
    parser.add_argument('--https-port', type=int, default=443)
    args = parser.parse_args()
    if any(port < 1 or port > 65535 for port in (args.http_port, args.https_port)):
        parser.error('Ports must be between 1 and 65535.')
    address = args.site.strip()
    parsed = urlsplit(address if '://' in address else 'https://' + address)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
            parsed.username or parsed.password or parsed.path not in ('', '/') or
            parsed.query or parsed.fragment or parsed.port or
            any(c.isspace() for c in address) or any(c in address for c in '\n\r$#{}')):
        parser.error('Provide an IP with http://, or a domain without a port/path.')
    target = Path(__file__).with_name('.env.production')
    content = Path(__file__).with_name('.env.example').read_text()
    content = content.replace('SITE_ADDRESS=http://localhost', 'SITE_ADDRESS=' + address.rstrip('/'))
    public_port = args.http_port if parsed.scheme == 'http' else args.https_port
    origin = parsed.scheme + '://' + parsed.netloc
    if public_port != (80 if parsed.scheme == 'http' else 443):
        origin += ':' + str(public_port)
    content = content.replace('SITE_ORIGIN=http://localhost', 'SITE_ORIGIN=' + origin)
    content = content.replace('HTTP_PORT=80', 'HTTP_PORT=' + str(args.http_port))
    content = content.replace('HTTPS_PORT=443', 'HTTPS_PORT=' + str(args.https_port))
    for key in ('API_KEY', 'DB_ADMIN_PASSWORD', 'DB_READER_PASSWORD', 'DB_INTAKE_PASSWORD', 'DB_OPS_PASSWORD', 'DB_NOTIFICATION_PASSWORD', 'OPS_BACKEND_KEY', 'OPS_SESSION_KEY'):
        content = content.replace(key + '=GENERATE_ME', key + '=' + secrets.token_hex(32))
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        output.write(content)
    print('Created deploy/.env.production (mode 600). Existing files are never overwritten.')


if __name__ == '__main__':
    try:
        main()
    except FileExistsError:
        raise SystemExit('Configuration already exists. Edit SITE_ADDRESS only; preserve database passwords and API_KEY.')
