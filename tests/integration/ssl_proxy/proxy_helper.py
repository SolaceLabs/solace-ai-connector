import asyncio
import threading
import time
import socket
import tempfile
from pathlib import Path
from mitmproxy import options, certs
from mitmproxy.tools.dump import DumpMaster 
import shutil
import signal
import subprocess
from contextlib import contextmanager
import sys 

class RequestCapture:
    def __init__(self):
        self.requests = []
        self.ready = threading.Event()
        self.error = None 

    def running(self):
        self.ready.set()

    def request(self, flow):
        self.requests.append({
            "method": flow.request.method,
            "url": flow.request.pretty_url,
            "headers": dict(flow.request.headers),
        })

def is_port_open(host, port, timeout=0.2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def get_free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def stop_mitmproxy(proc):
    try:
        proc.terminate()
        proc.join(timeout=2.0)
        # Force kill if still alive
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1.0)
    except Exception:
        pass  # Best effort cleanup

def start_mitmproxy(host="0.0.0.0", mode="regular"):
    """
    Starts mitmproxy in its own asyncio thread.
    Returns (thread, proxy_url, ca_path, capture).
    """
    confdir = Path(tempfile.mkdtemp(prefix="mitmproxy-conf-"))
    capture = RequestCapture()
    port = get_free_port()

    async def run_proxy_async():
        # Initialize options with the corrected 'mode' format (list of strings)
        opts = options.Options(listen_host=host, listen_port=port, confdir=str(confdir), mode=[f"{mode}"])
        
        # Initialize DumpMaster. It uses asyncio.get_running_loop() internally.
        master = DumpMaster(opts) 
        master.addons.add(capture)

        try:
            await master.run()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            capture.error = e
            print(f"Error in mitmproxy thread: {e}")

    def run_proxy_sync_wrapper():
        # Use asyncio.run() to manage the creation, running, and cleanup of the event loop.
        try:
            asyncio.run(run_proxy_async())
        except Exception as e:
            # Catch exceptions that might happen during asyncio.run() itself
            capture.error = e
            print(f"Error starting asyncio loop in thread: {e}")

    thread = threading.Thread(target=run_proxy_sync_wrapper, daemon=True)
    thread.start()

    # --- Robust Readiness Check (Monitor for error during timeout loop) ---
    start = time.time()
    while time.time() - start < 10:
        # Check if an error occurred in the thread
        if capture.error:
            raise RuntimeError(f"Mitmproxy failed to start in thread: {capture.error}") from capture.error

        # Use 127.0.0.1 for the check if the bind host is 0.0.0.0
        check_host = host if host != "0.0.0.0" else "127.0.0.1"
        if is_port_open(check_host, port):
            break
        time.sleep(0.1)
    else:
        # If we time out without an error being set, raise a generic timeout
        raise RuntimeError("Timed out waiting for mitmproxy to start")
    # ----------------------------------------------------

    # Ensure CA exists logic ... (assuming this part is correct from your side)
    ca_path = None
    for p in (
        confdir / "mitmproxy-ca.pem",
        confdir / "mitmproxy-ca-cert.pem",
        confdir / "mitmproxy-ca.crt",
        Path.home() / ".mitmproxy" / "mitmproxy-ca.pem",
    ):
        if p.exists():
            ca_path = str(p)
            break
    if not ca_path:
        store = certs.CertStore.from_store_id(str(confdir), "mitmproxy")
        ca_path = str(confdir / "mitmproxy-ca.pem")
        with open(ca_path, "wb") as f:
            f.write(store.default_ca.cert.to_pem())

    return thread, f"http://{host}:{port}", ca_path



# ================================Forward proxy helpers=================================

def generate_selfsigned_cert(hostname: str, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    key_path = out_dir / "server.key"
    cert_path = out_dir / "server.crt"
    subj = f"/CN={hostname}"
    subprocess.check_call([
        "openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048",
        "-keyout", str(key_path), "-out", str(cert_path),
        "-days", "365", "-subj", subj
    ])
    # create combined PEM for some servers (cert then key)
    pem_path = out_dir / "server.pem"
    with open(pem_path, "wb") as out:
        out.write(open(cert_path, "rb").read())
        out.write(open(key_path, "rb").read())
    return str(cert_path), str(key_path), str(pem_path)

@contextmanager
def start_https_server(host: str, port: int, cert_path: str, key_path: str):
    """
    Start a very small HTTPS server in a subprocess (http.server + ssl.wrap_socket).
    Yields when ready. Terminates subprocess on exit.
    """
    py = f"""
import http.server, ssl
class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type','text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

httpd = http.server.HTTPServer(('{host}', {port}), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(certfile={repr(cert_path)}, keyfile={repr(key_path)})
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

print('READY', flush=True)
httpd.serve_forever()
"""
    proc = subprocess.Popen([sys.executable, "-c", py],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # wait for READY
        start = time.time()
        while True:
            line = proc.stdout.readline()
            if "READY" in line:
                break
            if proc.poll() is not None:
                raise RuntimeError("HTTPS server failed to start: " + (proc.stderr.read() or "no output"))
            if time.time() - start > 8:
                raise RuntimeError("Timed out waiting for HTTPS server to be ready")
        yield
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

@contextmanager
def start_proxy_py(host: str = "127.0.0.1", port: int = 8899):
    """
    Start proxy.py as a forward proxy subprocess. Yields proxy_url "http://host:port".
    """
    cmd = [sys.executable, "-m", "proxy", "--hostname", host, "--port", str(port)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # wait until the TCP port is open
        start = time.time()
        while True:
            if proc.poll() is not None:
                raise RuntimeError("proxy.py exited prematurely: " + (proc.stderr.read() or ""))
            try:
                import socket
                with socket.create_connection((host, port), timeout=0.5):
                    break
            except OSError:
                pass
            if time.time() - start > 8:
                raise RuntimeError("Timed out waiting for proxy.py to start")
            time.sleep(0.1)
        yield f"http://{host}:{port}"
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

def write_bundle(path: Path, *pem_files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as out:
        for f in pem_files:
            out.write(open(f, "rb").read())
            out.write(b"\n")