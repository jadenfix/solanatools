"""Actual HTTP + SQLite + paper-engine integration; no provider mocks."""
import json
import http.client
from urllib.parse import urlparse
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import urllib.error
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

class WebReplay(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.start()
    def start(self):
        self.proc=subprocess.Popen([sys.executable,str(ROOT/'replay_web.py'),'--port','0','--db',self.tmp.name+'/runs.sqlite3'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        self.url=self.proc.stdout.readline().strip().split()[-1]
    def tearDown(self):
        self.proc.terminate();self.proc.wait(timeout=5);self.proc.stdout.close();self.tmp.cleanup()
    def request(self,path,data=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        with urllib.request.urlopen(req,timeout=10) as r:return r.status,json.loads(r.read())
    def test_demo_engine_and_download(self):
        status,result=self.request('/api/runs',{'source':'demo','name':'Test demo'})
        self.assertEqual(status,201);self.assertEqual(result['bars'],75);self.assertEqual(result['fills'],9)
        self.assertEqual(result['source'],'bundled_synthetic_fixture');self.assertEqual(result['mode'],'offline-paper')
        last=result['curve'][-1]
        self.assertAlmostEqual(last['cash']+last['quantity']*last['price'],result['final_equity'])
        self.assertAlmostEqual(sum(f['fee'] for f in result['ledger']),result['total_fees'])
        with urllib.request.urlopen(self.url+f"/api/runs/{result['id']}/download") as r:
            self.assertIn('attachment',r.headers['Content-Disposition']);self.assertEqual(json.loads(r.read()),result)
    def test_csv_config_and_restart_persistence(self):
        _,result=self.request('/api/runs',{'source':'csv','name':'Custom prices','csv':'timestamp,price\nt0,10\nt1,9\nt2,8\nt3,12\n','parameters':{'period':1,'fee_bps':20}})
        self.assertEqual(result['bars'],4);self.assertEqual(result['parameters']['period'],1);self.assertEqual(result['source'],'user_csv_unverified')
        self.proc.terminate();self.proc.wait(timeout=5);self.proc.stdout.close();self.start()
        self.assertEqual(self.request('/api/runs')[1]['items'][0]['name'],'Custom prices')
        self.assertEqual(self.request(f"/api/runs/{result['id']}")[1],result)
    def test_invalid_data_creates_no_saved_run(self):
        bad=[[],{'source':'fake'},{'name':' '},{'source':'csv','csv':'value\n12\n'},{'source':'csv','csv':'price\n0\n'}, {'source':'csv','csv':'price\nnan\n'}, {'source':'csv','csv':'price\n'}, {'parameters':{'period':True}}, {'parameters':{'period':1001}}, {'parameters':{'cash':float('nan')}}, {'parameters':{'max_exposure':2}}, {'parameters':{'fee_bps':'10'}}, {'parameters':{'stop_loss_pct':0}}]
        for data in bad:
            with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/runs',data)
            self.assertEqual(e.exception.code,400,data)
        self.assertEqual(self.request('/api/runs')[1]['items'],[])
    def test_origin_and_unknown_run(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/runs',{'source':'demo'},origin='https://bad.example')
        self.assertEqual(e.exception.code,403)
        for path in ['/api/runs/999','/api/runs/abc','/api/runs/1/foo','/../../replay_web.py']:
            with self.assertRaises(urllib.error.HTTPError) as e:self.request(path)
            self.assertEqual(e.exception.code,404)
    def test_size_and_bar_limits(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/api/runs',{'source':'csv','csv':'price\n'+'10\n'*10001})
        self.assertEqual(e.exception.code,400)
        # Send oversized declared length, not a megabyte after the server already rejects it.
        address=urlparse(self.url)
        conn=http.client.HTTPConnection(address.hostname,address.port,timeout=3)
        conn.putrequest('POST','/api/runs')
        conn.putheader('Content-Type','application/json')
        conn.putheader('Content-Length','1048577')
        conn.endheaders()
        response=conn.getresponse()
        self.assertEqual(response.status,413)
        response.read();conn.close()
    def test_static_routes(self):
        for path,mime in [('/','text/html'),('/workbench.js','text/javascript'),('/workbench.css','text/css')]:
            with urllib.request.urlopen(self.url+path) as r:
                self.assertIn(mime,r.headers['Content-Type']);self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])
        with urllib.request.urlopen(self.url+'/favicon.ico') as response:
            self.assertEqual(response.status,204);self.assertEqual(response.read(),b'')

if __name__=='__main__':unittest.main()
