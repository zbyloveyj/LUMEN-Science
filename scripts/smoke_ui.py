"""Open the real desktop renderer, await the UI ready signal, then close it."""
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run
import webview

ready = threading.Event()
failures = []
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
                    def exercise():
                        def js(code):
                            return window.evaluate_js(code)
                        def wait_for(code):
                            for _ in range(100):
                                if js(code):return
                                time.sleep(.1)
                            raise AssertionError(code)
                        def nav(view):
                            js("document.querySelector('[data-view="+view+"]').click()")
                        try:
                            js("document.querySelector('[data-action=new-project]').click()")
                            wait_for("document.querySelector('#modal').open")
                            js("document.querySelector('#modal [value=cancel]').click()")
                            wait_for("!document.querySelector('#modal').open")
                            print('PASS: empty required dialog can be cancelled',flush=True)
                            nav('settings')
                            wait_for("!!document.querySelector('#settings-form')")
                            js("document.querySelector('[name=model]').value='unsaved-fixture';document.querySelector('[name=model]').dispatchEvent(new Event('input',{bubbles:true}))")
                            nav('overview')
                            wait_for("document.querySelector('#modal').open")
                            js("document.querySelector('#modal [value=cancel]').click()")
                            wait_for("!document.querySelector('#modal').open")
                            assert js("document.querySelector('[name=model]').value") == 'unsaved-fixture'
                            print('PASS: cancel navigation preserves settings',flush=True)
                            nav('reports')
                            wait_for("document.querySelector('#modal').open")
                            js("document.querySelector('#modal [value=save]').click()")
                            wait_for("!!document.querySelector('#report-content')")
                            js("document.querySelector('[data-action=generate-report]').click()")
                            wait_for("!document.querySelector('#report-content').disabled")
                            js("document.querySelector('#report-content').value='UI autosave fixture';document.querySelector('#report-content').dispatchEvent(new Event('input',{bubbles:true}))")
                            nav('overview')
                            wait_for("!document.querySelector('#report-content')")
                            nav('reports')
                            wait_for("!!document.querySelector('[data-action=edit-report]')")
                            js("document.querySelector('[data-action=edit-report]').click()")
                            wait_for("document.querySelector('#report-content').value==='UI autosave fixture'")
                            print('PASS: report saved on navigation and restored',flush=True)
                            nav('notebook')
                            wait_for("!!document.querySelector('.code-editor')")
                            js("document.querySelector('.code-editor').value='print(7654321)'")
                            js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'s',ctrlKey:true,bubbles:true}))")
                            wait_for("document.querySelector('#toast').textContent==='编辑内容已保存'")
                            nav('overview')
                            wait_for("!document.querySelector('.code-editor')")
                            nav('notebook')
                            wait_for("document.querySelector('.code-editor')?.value==='print(7654321)'")
                            print('PASS: notebook keyboard save persists code',flush=True)
                        except Exception as exc:
                            failures.append(str(exc))
                        finally:
                            window.destroy()
                    threading.Thread(target=exercise,daemon=True).start()
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

if failures:
    raise SystemExit("UI checks failed: " + str(failures))
