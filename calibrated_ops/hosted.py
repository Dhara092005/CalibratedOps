"""Protected single-user deployment behind Caddy and the host's HTTPS edge.

The normal local CLI stays loopback-only. No account database is introduced.
"""
import os
from pathlib import Path
import re
import signal
import subprocess
from threading import Event, Thread
from urllib.parse import urlsplit

from .server import make_server


def configuration(env):
    origin=env.get('CALIBRATED_PUBLIC_ORIGIN') or env.get('RENDER_EXTERNAL_URL','')
    parsed=urlsplit(origin)
    local_test=(env.get('CALIBRATED_LOCAL_TEST')=='1' and parsed.hostname in ('127.0.0.1','localhost'))
    if (any(ord(char)<33 for char in origin)
            or parsed.scheme not in (('http','https') if local_test else ('https',))
            or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment
            or not re.fullmatch(r'[A-Za-z0-9.-]+(?::[0-9]+)?',parsed.netloc)):
        raise ValueError('Set CALIBRATED_PUBLIC_ORIGIN to the exact HTTPS origin, without a trailing slash.')
    password=env.get('CALIBRATED_PASSWORD','')
    if not 16<=len(password.encode('utf-8'))<=72 or '\n' in password or '\r' in password:
        raise ValueError('Set CALIBRATED_PASSWORD to a secret of 16 to 72 UTF-8 bytes, without newlines.')
    port=int(env.get('PORT','10000'))
    if not 1024<=port<=65535 or port==8767:
        raise ValueError('PORT must be between 1024 and 65535 and differ from the internal port 8767.')
    database=Path(env.get('CALIBRATED_DATABASE','/var/data/calibrated_ops.sqlite3'))
    if not database.is_absolute():
        raise ValueError('CALIBRATED_DATABASE must be an absolute persistent-storage path.')
    return dict(origin=origin,hostname=parsed.hostname,password=password,port=port,database=database)


def gateway_config(config,hashed_password):
    if not re.fullmatch(r'\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}',hashed_password):
        raise ValueError('Caddy did not return a valid bcrypt password hash.')
    return '''{
    admin off
    auto_https off
    persist_config off
}
http://:%s {
    route {
        @wrongHost not host %s
        respond @wrongHost "Invalid host" 403
        handle /healthz {
            reverse_proxy 127.0.0.1:8767 {
                header_up Host 127.0.0.1:8767
                header_up -Authorization
            }
        }
        handle {
            basic_auth {
                admin %s
            }
            request_body {
                max_size 13MB
            }
            reverse_proxy 127.0.0.1:8767 {
                header_up Host 127.0.0.1:8767
                header_up -Authorization
            }
        }
    }
}
''' % (config['port'],config['hostname'],hashed_password)


def main():
    try:
        config=configuration(os.environ)
        demo=os.environ.get('CALIBRATED_DEMO')=='1'
        if demo:
            # The free demonstration must never consume a configured paid API key.
            os.environ.pop('OPENAI_API_KEY',None)
        # Password is sent over stdin, never command arguments, files, or logs.
        child_env={k:v for k,v in os.environ.items() if k not in ('CALIBRATED_PASSWORD','OPENAI_API_KEY')}
        result=subprocess.run(['caddy','hash-password','--algorithm','bcrypt'],
                              input=config['password']+'\n',text=True,capture_output=True,
                              check=True,env=child_env,timeout=30)
        gateway=gateway_config(config,result.stdout.strip())
        del config['password']
        config['database'].parent.mkdir(parents=True,exist_ok=True)
        if os.environ.get('CALIBRATED_SEED_PUBLIC','1')=='1':
            from .storage import Store
            from .public_data import load_public_dataset
            from scripts.prepare_research_materials import additional_dataset
            store=Store(str(config['database']))
            name,data=load_public_dataset()
            store.save_dataset(name,data)
            for version in ('v1','v2'):
                source=Path(__file__).parent/'data'/f'additional_public_incidents_{version}.json'
                name,data=additional_dataset(source)
                store.save_dataset(name,data)
        server=make_server(8767,str(config['database']),public_origin=config['origin'],demo=demo)
    except (ValueError,OSError,subprocess.SubprocessError):
        raise SystemExit('Hosted startup failed. Check HTTPS origin, password, persistent path, and Caddy installation. No public listener was started.')
    worker=Thread(target=server.serve_forever,daemon=True)
    worker.start()
    stopped=Event()
    def stop(*_):stopped.set()
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    proxy=None
    try:
        proxy=subprocess.Popen(['caddy','run','--config','-','--adapter','caddyfile'],
                               stdin=subprocess.PIPE,text=True,env=child_env)
        proxy.stdin.write(gateway)
        proxy.stdin.close()
        print('Protected single-user workspace starting. Database uses the configured persistent path.',flush=True)
        while not stopped.wait(1):
            if proxy.poll() is not None or not worker.is_alive():
                raise SystemExit('Hosted worker stopped; restart the service.')
    finally:
        if proxy and proxy.poll() is None:
            proxy.terminate()
            try:proxy.wait(timeout=10)
            except subprocess.TimeoutExpired:proxy.kill();proxy.wait()
        server.shutdown()
        worker.join(timeout=10)
        server.server_close()


if __name__=='__main__':main()
