"""Loopback-only replay workbench. Uses the existing paper engine; no RPC or wallet."""
import argparse
import csv
import io
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from core.engine.paper import PaperExecutionEngine
from core.strategies.rsi_momentum import RSIMomentumStrategy

ROOT = Path(__file__).resolve().parent


def connect(db):
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL, result TEXT NOT NULL)')
    conn.commit()
    return conn


def replay(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object')
    name = data.get('name', 'Untitled replay')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError('Run name must be 1–80 characters')
    source = data.get('source', 'demo')
    if source == 'demo':
        text = (ROOT / 'fixtures' / 'synthetic_prices.csv').read_text()
        provenance = 'bundled_synthetic_fixture'
    elif source == 'csv':
        text = data.get('csv')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('CSV text is required')
        provenance = 'user_csv_unverified'
    else:
        raise ValueError('Source must be demo or csv')
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or 'price' not in reader.fieldnames:
        raise ValueError('CSV needs a price column; timestamp is optional')
    rows = []
    for row in reader:
        if len(rows) >= 10000:
            raise ValueError('Maximum 10000 price bars per local replay')
        if len(str(row.get('timestamp', ''))) > 120:
            raise ValueError('Timestamp must be at most 120 characters')
        rows.append(row)
    params = data.get('parameters', {})
    if not isinstance(params, dict):
        raise ValueError('Parameters must be a JSON object')
    values = {}
    for key, default in [('cash', 10000), ('max_exposure', .25), ('fee_bps', 10), ('stop_loss_pct', .05), ('take_profit_pct', .10)]:
        raw = params.get(key, default)
        if isinstance(raw, bool) or not isinstance(raw, (float, int)):
            raise ValueError(f'{key} must be numeric')
        values[key] = float(raw)
    period = params.get('period', 14)
    if isinstance(period, bool) or not isinstance(period, int) or not 1 <= period <= 1000:
        raise ValueError('RSI period must be an integer between 1 and 1000')
    if values['cash'] > 1e12 or values['take_profit_pct'] > 100:
        raise ValueError('Configuration exceeds local replay limits')
    engine = PaperExecutionEngine(RSIMomentumStrategy(period), **values)
    result = engine.run(rows)
    result.update(name=name.strip(), source=provenance, parameters=dict(period=period, **values),
                  total_fees=sum(fill['fee'] for fill in result['ledger']))
    # Engine may reject non-finite prices; also reject overflow from otherwise huge finite inputs.
    json.dumps(result, allow_nan=False)
    return result


def handler(db):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, payload, mime='application/json', download=False):
            body = json.dumps(payload, allow_nan=False).encode() if mime == 'application/json' else payload
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'")
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="paper-replay.json"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/api/health':
                return self.send(200, {'ok': True, 'mode': 'offline-paper'})
            if path == '/api/runs':
                with connect(db) as conn:
                    rows = conn.execute('SELECT id,name,created_at FROM runs ORDER BY id DESC LIMIT 100').fetchall()
                return self.send(200, {'items': [dict(zip(['id','name','created_at'],row)) for row in rows]})
            if path.startswith('/api/runs/'):
                parts = path.strip('/').split('/')
                if len(parts) not in (3,4) or not parts[2].isdigit() or (len(parts)==4 and parts[3]!='download'):
                    return self.send(404, {'error': 'Run not found'})
                with connect(db) as conn:
                    row = conn.execute('SELECT result FROM runs WHERE id=?', (parts[2],)).fetchone()
                if not row:
                    return self.send(404, {'error': 'Run not found'})
                return self.send(200, json.loads(row[0]), download=len(parts)==4)
            files = {'/': ('index.html','text/html; charset=utf-8'), '/workbench.js': ('workbench.js','text/javascript; charset=utf-8'), '/workbench.css': ('workbench.css','text/css; charset=utf-8')}
            if path in files:
                name,mime = files[path]
                return self.send(200, (ROOT/'web'/name).read_bytes(), mime)
            return self.send(404, {'error': 'Not found'})

        def do_POST(self):
            if self.path != '/api/runs':
                return self.send(404, {'error': 'Not found'})
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host',''):
                return self.send(403, {'error': 'Cross-origin writes disabled'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 1 <= length <= 1048576:
                    return self.send(413, {'error': 'Request must be 1 byte–1 MiB'})
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    return self.send(415, {'error': 'Expected application/json'})
                result = replay(json.loads(self.rfile.read(length)))
            except (ValueError, TypeError, KeyError, OverflowError, csv.Error) as exc:
                return self.send(400, {'error': str(exc)})
            created = datetime.now(timezone.utc).isoformat()
            with connect(db) as conn:
                cur = conn.execute('INSERT INTO runs(name,created_at,result) VALUES(?,?,?)', (result['name'],created,json.dumps(result,allow_nan=False)))
                result.update(id=cur.lastrowid, created_at=created)
                conn.execute('UPDATE runs SET result=? WHERE id=?', (json.dumps(result,allow_nan=False),result['id']))
            return self.send(201, result)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8082)
    parser.add_argument('--db', default=str(ROOT/'replays.sqlite3'))
    args = parser.parse_args()
    with connect(args.db):
        pass
    server = ThreadingHTTPServer(('127.0.0.1',args.port),handler(args.db))
    print(f'Replay workbench: http://127.0.0.1:{server.server_port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
