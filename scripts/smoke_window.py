"""Open the real desktop renderer, await the UI ready signal, then close it."""
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run
import webview

ready = threading.Event()
create_window = webview.create_window

def instrument_window(*args, **kwargs):
    window = create_window(*args, **kwargs)
    expose = window.expose
    def instrument_expose(*functions):
        wrapped = []
        for function in functions:
            if function.__name__ == 'lumen_ready':
                def lumen_ready(original=function):
                    original()
                    ready.set()
                    threading.Timer(2, window.destroy).start()
                wrapped.append(lumen_ready)
            else:
                wrapped.append(function)
        expose(*wrapped)
    window.expose = instrument_expose
    return window

webview.create_window = instrument_window
with tempfile.TemporaryDirectory(prefix='lumen-window-') as directory:
    root = Path(directory)
    app = run.Workbench(root)
    with run.LocalServer(('127.0.0.1', 0), app, run.resources() / 'web') as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = run.desktop_window('http://127.0.0.1:' + str(server.server_port), root)
            if not result or not ready.is_set():
                raise SystemExit((root / 'desktop-startup.log').read_text(encoding='utf-8'))
            print('PASS: native renderer loaded the workbench and received lumen_ready')
        finally:
            server.shutdown()
            thread.join(timeout=5)
            app.execution.shutdown()
