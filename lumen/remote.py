from __future__ import annotations

import base64
import hashlib
import json
import posixpath
import shlex
import socket
import stat
import threading
import time
from pathlib import Path

from .files import MAX_FILE, safe_path
from .secrets import Secrets
from .store import uid, now


def fingerprint(key):
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")


def paramiko_module():
    try:
        import paramiko
        return paramiko
    except ImportError:
        raise ValueError("SSH 组件尚未安装；请按安装说明安装 paramiko") from None


def validate_host(host, port):
    if not isinstance(host, str) or not host.strip() or len(host) > 250 or any(c in host for c in "\r\n\t /\\"):
        raise ValueError("服务器地址格式无效")
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("SSH 端口需要为 1–65535")
    return host.strip(), port


class Remote:
    def __init__(self, app):
        self.app = app
        self.probes = {}
        self.jobs = {}

    def list(self):
        profiles = self.app.store.setting("ssh_profiles", [])
        return {"profiles": profiles, "available": self.available()}

    @staticmethod
    def available():
        try:
            paramiko_module()
            return True
        except ValueError:
            return False

    def probe(self, host, port):
        module = paramiko_module()
        host, port = validate_host(host, port)
        transport = module.Transport(socket.create_connection((host, port), timeout=12))
        try:
            transport.start_client(timeout=12)
            key = transport.get_remote_server_key()
            result = {"host": host, "port": port, "fingerprint": fingerprint(key),
                      "key_type": key.get_name(), "key": key.get_base64(), "time": time.monotonic()}
            token = uid()
            self.probes[token] = result
            while len(self.probes) > 40:
                self.probes.pop(next(iter(self.probes)))
            return {"probe_id": token, "fingerprint": result["fingerprint"], "key_type": result["key_type"]}
        finally:
            transport.close()

    def save(self, p):
        host, port = validate_host(p["host"], p.get("port", 22))
        username = str(p.get("username", "")).strip()
        if not username or any(c in username for c in "\r\n\x00"):
            raise ValueError("请填写服务器用户名")
        profiles = self.app.store.setting("ssh_profiles", [])
        old = next((x for x in profiles if x["id"] == p.get("id")), None)
        probe = self.probes.get(p.get("probe_id", ""))
        if probe:
            if probe["host"] != host or probe["port"] != port or time.monotonic()-probe["time"] > 900:
                raise ValueError("主机指纹核对已过期，请重新检测")
        elif old and old["host"] == host and old["port"] == port:
            probe = old
        else:
            raise ValueError("请先检测并核对服务器主机指纹")
        key_file = str(p.get("key_file", "")).strip()
        if key_file and not Path(key_file).is_file():
            raise ValueError("SSH 私钥文件不存在")
        profile_id = old["id"] if old else uid()
        profile = {"id": profile_id, "name": str(p.get("name") or host)[:100],
                   "host": host, "port": port, "username": username,
                   "root": str(p.get("root") or ".")[:1000], "key_file": key_file,
                   "use_agent": bool(p.get("use_agent", False)),
                   "fingerprint": probe["fingerprint"], "key_type": probe["key_type"],
                   "key": probe["key"]}
        for field in ("password", "passphrase"):
            if p.get(field):
                Secrets(self.app.store, "ssh." + profile_id + "." + field).set(str(p[field]))
        profiles = [x for x in profiles if x["id"] != profile_id] + [profile]
        self.app.store.set_setting("ssh_profiles", profiles)
        return {"saved": True, "id": profile_id}

    def profile(self, profile_id):
        value = next((x for x in self.app.store.setting("ssh_profiles", []) if x["id"] == profile_id), None)
        if not value:
            raise ValueError("服务器配置不存在")
        return value

    def connect(self, profile_id):
        module = paramiko_module()
        profile = self.profile(profile_id)
        expected = profile["fingerprint"]
        class PinnedHostKey(module.MissingHostKeyPolicy):
            def missing_host_key(self, client, hostname, key):
                if fingerprint(key) != expected:
                    raise ValueError("服务器主机指纹已改变，连接已拒绝；请核对服务器身份")
        client = module.SSHClient()
        client.set_missing_host_key_policy(PinnedHostKey())
        try:
            client.connect(hostname=profile["host"], port=profile["port"], username=profile["username"],
                           password=Secrets(self.app.store, "ssh."+profile_id+".password").get() or None,
                           passphrase=Secrets(self.app.store, "ssh."+profile_id+".passphrase").get() or None,
                           key_filename=profile["key_file"] or None, look_for_keys=False,
                           allow_agent=profile["use_agent"], timeout=12, banner_timeout=12, auth_timeout=15)
            return client
        except Exception:
            client.close()
            raise

    @staticmethod
    def remote_path(sftp, root, relative, parent=False):
        if not isinstance(relative, str) or "\x00" in relative:
            raise ValueError("远程路径无效")
        root = sftp.normalize(root)
        if posixpath.isabs(relative) or ".." in relative.split("/"):
            raise ValueError("请使用服务器工作目录内的相对路径")
        path = posixpath.join(root, relative or ".")
        canonical = posixpath.join(sftp.normalize(posixpath.dirname(path)), posixpath.basename(path)) if parent else sftp.normalize(path)
        if canonical != root and not canonical.startswith(root.rstrip("/") + "/"):
            raise ValueError("远程路径超出所选工作目录")
        return canonical

    def test(self, profile_id):
        client = self.connect(profile_id)
        try:
            sftp = client.open_sftp()
            try:
                root = sftp.normalize(self.profile(profile_id)["root"])
                sftp.stat(root)
                return {"connected": True, "root": root, "fingerprint": self.profile(profile_id)["fingerprint"],
                        "message": "SSH 认证与 SFTP 工作目录检查通过"}
            finally:
                sftp.close()
        finally:
            client.close()

    def files(self, profile_id, relative=""):
        client = self.connect(profile_id)
        try:
            sftp = client.open_sftp()
            try:
                root = self.profile(profile_id)["root"]
                path = self.remote_path(sftp, root, relative)
                entries = sftp.listdir_attr(path)
                return {"path": relative, "files": [{"name": x.filename, "bytes": x.st_size,
                         "directory": stat.S_ISDIR(x.st_mode), "symlink": stat.S_ISLNK(x.st_mode),
                         "path": posixpath.join(relative, x.filename)} for x in entries[:300]],
                        "truncated": len(entries) > 300}
            finally:
                sftp.close()
        finally:
            client.close()

    def transfer(self, project_id, profile_id, direction, local, remote):
        project = self.app.project(project_id)
        client = self.connect(profile_id)
        try:
            sftp = client.open_sftp()
            try:
                path = self.remote_path(sftp, self.profile(profile_id)["root"], remote, direction == "upload")
                if direction == "upload":
                    source = safe_path(project["path"], local, True)
                    if not source.is_file() or source.stat().st_size > MAX_FILE:
                        raise ValueError("单次上传支持不超过32 MiB的普通文件")
                    # Exclusive creation avoids silently replacing an existing remote file.
                    with source.open("rb") as inp, sftp.open(path, "wx") as out:
                        while chunk := inp.read(128 * 1024):
                            out.write(chunk)
                    return {"direction": direction, "remote": remote, "bytes": source.stat().st_size}
                if direction != "download":
                    raise ValueError("未知传输方向")
                info = sftp.stat(path)
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
                    raise ValueError("单次下载支持不超过32 MiB的普通文件")
                relative = "outputs/remote-" + uid() + "/" + posixpath.basename(path)
                dest = safe_path(project["path"], relative)
                dest.parent.mkdir(parents=True, exist_ok=False)
                count = 0
                with sftp.open(path, "rb") as inp, dest.open("xb") as out:
                    while chunk := inp.read(128 * 1024):
                        count += len(chunk)
                        if count > MAX_FILE:
                            raise ValueError("下载期间文件变大，超过32 MiB上限")
                        out.write(chunk)
                return {"direction": direction, "path": relative, "bytes": count}
            finally:
                sftp.close()
        finally:
            client.close()

    def execute(self, project_id, profile_id, command, timeout=300):
        project = self.app.project(project_id)
        profile = self.profile(profile_id)
        if not isinstance(command, str) or not command.strip() or len(command) > 100_000:
            raise ValueError("请输入有效的远程命令")
        run_id = self.app.store.new_run(project_id, None, "bash", command, "远程 · " + profile["name"],
                kind="remote", remote={"host":profile["host"],"port":profile["port"],"root":profile["root"]},
                provenance_scope="远程命令、状态和有界日志；未捕获远程输入输出快照")
        event = threading.Event()
        self.jobs[run_id] = event
        folder = Path(project["path"]) / ".lumen" / "runs" / run_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "code.sh").write_text(command,encoding="utf-8")
        def work():
            start=time.monotonic();client=None;channel=None
            try:
                if event.is_set():
                    self.app.store.update_run(run_id,"cancelled")
                    return
                client=self.connect(profile_id)
                sftp=client.open_sftp()
                try: root=sftp.normalize(profile["root"])
                finally:sftp.close()
                if event.is_set():
                    self.app.store.update_run(run_id,"cancelled")
                    return
                channel=client.get_transport().open_session(timeout=15)
                channel.exec_command("cd -- "+shlex.quote(root)+" && "+command)
                self.app.store.update_run(run_id,"running",environment={"host":profile["host"],"root":root})
                deadline=time.monotonic()+max(5,min(int(timeout),3600))
                while not channel.exit_status_ready():
                    if event.is_set() or time.monotonic()>deadline:
                        channel.close()
                        self.app.store.update_run(run_id,"interrupted",
                            error="连接等待已停止；远端进程是否结束未知，请在服务器核查。")
                        return
                    if channel.recv_ready():
                        self.app.store.append_output(run_id,{"type":"stream","name":"stdout","text":channel.recv(32768).decode("utf-8","replace")})
                    if channel.recv_stderr_ready():
                        self.app.store.append_output(run_id,{"type":"stream","name":"stderr","text":channel.recv_stderr(32768).decode("utf-8","replace")})
                    time.sleep(.08)
                while channel.recv_ready():
                    self.app.store.append_output(run_id,{"type":"stream","name":"stdout","text":channel.recv(32768).decode("utf-8","replace")})
                while channel.recv_stderr_ready():
                    self.app.store.append_output(run_id,{"type":"stream","name":"stderr","text":channel.recv_stderr(32768).decode("utf-8","replace")})
                code=channel.recv_exit_status()
                self.app.store.update_run(run_id,"success" if code==0 else "failed",exit_code=code,
                                          error=None if code==0 else "远程退出码 "+str(code))
            except Exception as exc:
                self.app.store.update_run(run_id,"failed",error=str(exc))
            finally:
                if channel:channel.close()
                if client:client.close()
                self.jobs.pop(run_id,None)
                self.app.store.update_run(run_id,duration=round(time.monotonic()-start,3))
                (folder/"manifest.json").write_text(json.dumps(self.app.store.run(run_id),ensure_ascii=False,indent=2),encoding="utf-8")
        threading.Thread(target=work,daemon=True).start()
        return self.app.store.run(run_id)
