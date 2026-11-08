from __future__ import annotations

import json
import os
import posixpath
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from lumen.app import Workbench
from lumen.remote import paramiko_module
paramiko=paramiko_module()


class FixtureSFTP(paramiko.SFTPServerInterface):
    def __init__(self,server,*args,root=None,**kwargs):
        super().__init__(server,*args,**kwargs);self.root=Path(root).resolve()
    def local(self,path):
        p=(self.root/str(path).lstrip("/")).resolve()
        if p!=self.root and self.root not in p.parents:raise OSError("outside")
        return p
    def canonicalize(self,path):return posixpath.normpath("/"+path.lstrip("/"))
    def list_folder(self,path):
        try:
            result=[]
            for p in self.local(path).iterdir():
                a=paramiko.SFTPAttributes.from_stat(p.stat());a.filename=p.name;result.append(a)
            return result
        except OSError as e:return paramiko.SFTPServer.convert_errno(e.errno or 13)
    def stat(self,path):
        try:return paramiko.SFTPAttributes.from_stat(self.local(path).stat())
        except OSError as e:return paramiko.SFTPServer.convert_errno(e.errno or 2)
    lstat=stat
    def open(self,path,flags,attr):
        try:
            p=self.local(path)
            if flags&os.O_CREAT:
                file=p.open("xb" if flags&os.O_EXCL else "wb")
            else:file=p.open("rb")
            handle=paramiko.SFTPHandle(flags)
            if flags&(os.O_WRONLY|os.O_RDWR):handle.writefile=file
            else:handle.readfile=file
            return handle
        except OSError as e:return paramiko.SFTPServer.convert_errno(e.errno or 13)


class FixtureSSH(paramiko.ServerInterface):
    def check_auth_password(self,username,password):
        return paramiko.AUTH_SUCCESSFUL if (username,password)==("tester","local-fixture-only") else paramiko.AUTH_FAILED
    def get_allowed_auths(self,username):return "password"
    def check_channel_request(self,kind,chanid):
        return paramiko.OPEN_SUCCEEDED if kind=="session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
    def check_channel_exec_request(self,channel,command):
        def work():
            time.sleep(.1)
            try:
                if b"long-test" in command:time.sleep(2)
                channel.send(b"remote-fixture-42\n");channel.send_exit_status(0)
            except Exception:pass
            finally:channel.close()
        threading.Thread(target=work,daemon=True).start()
        return True


class RemoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (BASE/"test-results").mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix="ssh-fixture-",dir=BASE/"test-results")
        cls.root=Path(cls.temp.name)
        cls.remote_root=cls.root/"server";cls.remote_root.mkdir()
        (cls.remote_root/"source.txt").write_text("fixture source",encoding="utf-8")
        cls.key=paramiko.RSAKey.generate(2048)
        cls.listener=socket.socket();cls.listener.bind(("127.0.0.1",0));cls.listener.listen(12)
        cls.port=cls.listener.getsockname()[1];cls.stop=threading.Event();cls.transports=[]
        def client(sock):
            transport=paramiko.Transport(sock);cls.transports.append(transport)
            try:
                transport.add_server_key(cls.key)
                transport.set_subsystem_handler("sftp",paramiko.SFTPServer,FixtureSFTP,root=cls.remote_root)
                transport.start_server(server=FixtureSSH())
                while transport.is_active() and not cls.stop.is_set():time.sleep(.05)
            except Exception:pass
            finally:transport.close()
        def accept():
            while not cls.stop.is_set():
                try:sock,_=cls.listener.accept()
                except OSError:break
                threading.Thread(target=client,args=(sock,),daemon=True).start()
        threading.Thread(target=accept,daemon=True).start()
        cls.app=Workbench(cls.root/"app")
        boot=cls.app.dispatch("bootstrap",{});cls.pid=boot["project_id"]
        probe=cls.app.remote.probe("127.0.0.1",cls.port)
        cls.profile=cls.app.remote.save({"host":"127.0.0.1","port":cls.port,"username":"tester",
            "password":"local-fixture-only","root":"/","name":"local SSH fixture","probe_id":probe["probe_id"]})["id"]

    @classmethod
    def tearDownClass(cls):
        cls.stop.set();cls.listener.close()
        for transport in cls.transports:transport.close()
        cls.app.execution.shutdown();time.sleep(.2);cls.temp.cleanup()

    def test_host_identity_authentication_and_listing(self):
        result=self.app.remote.test(self.profile)
        self.assertTrue(result["connected"])
        files=self.app.remote.files(self.profile)
        self.assertIn("source.txt",[x["name"] for x in files["files"]])

    def test_sftp_download_upload_and_no_overwrite(self):
        result=self.app.remote.transfer(self.pid,self.profile,"download","","source.txt")
        path=Path(self.app.project(self.pid)["path"])/result["path"]
        self.assertEqual(path.read_text(encoding="utf-8"),"fixture source")
        self.app.remote.transfer(self.pid,self.profile,"upload","data/synthetic_experiment.csv","uploaded.csv")
        self.assertTrue((self.remote_root/"uploaded.csv").is_file())
        with self.assertRaises(OSError):
            self.app.remote.transfer(self.pid,self.profile,"upload","data/synthetic_experiment.csv","uploaded.csv")
        with self.assertRaises(ValueError):self.app.remote.files(self.profile,"../escape")

    def test_remote_command_log_and_exit_status(self):
        run=self.app.remote.execute(self.pid,self.profile,"printf remote-fixture")
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            result=self.app.store.run(run["id"])
            if result["status"] not in ("queued","running"):break
            time.sleep(.1)
        self.assertEqual(result["status"],"success",str(result["detail"]))
        self.assertIn("remote-fixture-42",str(result["detail"]["outputs"]))
        self.assertEqual(result["detail"]["exit_code"],0)

    def test_changed_host_key_is_rejected(self):
        original=self.app.store.setting("ssh_profiles")
        altered=json.loads(json.dumps(original));altered[0]["fingerprint"]="SHA256:wrong"
        self.app.store.set_setting("ssh_profiles",altered)
        try:
            with self.assertRaises(ValueError):self.app.remote.test(self.profile)
        finally:self.app.store.set_setting("ssh_profiles",original)


if __name__=="__main__":unittest.main(verbosity=2)
