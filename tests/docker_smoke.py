"""Isolated container integration check; uses synthetic answers and no live API.

Run after docker build -t calibratedops:deploy-test .
"""
import base64
import json
import os
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid


def docker(*args,**kwargs):
    return subprocess.check_output(['docker',*args],text=True,**kwargs).strip()


def main():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    name='calibratedops-qa-'+uuid.uuid4().hex[:12]
    volume=name+'-data'
    origin=f'http://127.0.0.1:{port}'
    password=secrets.token_urlsafe(24)
    env=dict(os.environ,CALIBRATED_PASSWORD=password)
    auth='Basic '+base64.b64encode(('admin:'+password).encode()).decode()
    def request(path,body=None,headers=None):
        headers=headers or {}
        if body is not None:headers=dict(headers,**{'Content-Type':'application/json'})
        req=urllib.request.Request(origin+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=10) as response:return response.status,response.read()
        except urllib.error.HTTPError as error:return error.code,error.read()
    def healthy():
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            try:
                if request('/healthz')[0]==200:return
            except OSError:pass
            time.sleep(.5)
        raise AssertionError('Container did not become healthy')
    docker('volume','create',volume)
    def launch(persistent,public=False):
        mount=['--mount',f'type=volume,source={volume},target=/var/data'] if persistent else []
        access=['-e','CALIBRATED_PUBLIC_DEMO=1'] if public else ['-e','CALIBRATED_PASSWORD']
        docker('run','-d','--name',name,'-p',f'127.0.0.1:{port}:10000',*mount,
               *access,'-e','CALIBRATED_LOCAL_TEST=1','-e','CALIBRATED_DEMO=1',
               '-e',f'CALIBRATED_PUBLIC_ORIGIN={origin}','calibratedops:deploy-test',env=env)
    try:
        launch(True)
        healthy()
        for path in ('/','/app.js','/api/state','/api/export','/api/research-readiness'):
            assert request(path)[0]==401,path
        assert request('/api/state',headers={'Authorization':'Basic invalid'})[0]==401
        assert request('/api/state',headers={'Authorization':auth,'Host':'attacker.invalid'})[0]==403
        status,body=request('/api/state',headers={'Authorization':auth})
        assert status==200
        state=json.loads(body);assert len(state['datasets'])==3
        assert state['ephemeral_demo'] is True
        assert state['ai_configured'] is False
        status,export=request('/api/export',headers={'Authorization':auth})
        assert status==200 and 'not genuine research observations' in json.loads(export)['notice']
        assert sum(d['metadata']['records'] for d in state['datasets'])==28
        payload=dict(title='Synthetic deployment QA',evidence='Temporary QA latency observation.',risk='low',agent='rules')
        headers={'Authorization':auth,'X-Review-Token':state['token'],'Origin':'https://attacker.invalid'}
        assert request('/api/incidents',payload,headers)[0]==403
        headers['Origin']=origin
        status,body=request('/api/incidents',payload,headers);assert status==201
        ident=json.loads(body)['id']
        docker('restart',name);healthy()
        status,body=request('/api/state',headers={'Authorization':auth});assert status==200
        state=json.loads(body)
        assert any(i['id']==ident for i in state['incidents'])
        assert len(state['datasets'])==3,'Restart duplicated bundled datasets'
        assert request('/api/export')[0]==401
        docker('rm','-f',name)
        launch(False,public=True);healthy()
        status,body=request('/api/state')
        fresh=json.loads(body)
        assert status==200 and fresh['ephemeral_demo'] is True
        assert len(fresh['datasets'])==3 and not fresh['incidents']
        assert request('/')[0]==200
        assert request('/app.js')[0]==200
        assert request('/api/export')[0]==200
        headers={'X-Review-Token':fresh['token'],'Origin':'https://attacker.invalid'}
        assert request('/api/incidents',payload,headers)[0]==403
        headers['Origin']=origin
        assert request('/api/incidents',payload,headers)[0]==201
        assert fresh['ai_configured'] is False
        print('Container checks passed: private authentication, public password-free demo, host/origin checks, writes, seeded cases, volume persistence and ephemeral reset.')
    finally:
        subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(['docker','volume','rm',volume],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=='__main__':main()
