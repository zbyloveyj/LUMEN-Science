"""Credentials are encrypted with Windows DPAPI; other systems keep keys in memory."""
import base64
import ctypes
import os
from ctypes import wintypes


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt(value, decrypt=False):
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = Blob()
    if decrypt:
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(source), "LUMEN Science", None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise OSError("Windows 凭证加密操作失败")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


class Secrets:
    def __init__(self, store, name="credential"):
        self.store = store
        self.name = name
        if not hasattr(store,"secret_memory"):
            store.secret_memory={}

    def set(self, value):
        self.store.secret_memory[self.name] = value
        if os.name == "nt":
            self.store.set_setting(self.name, base64.b64encode(_crypt(value.encode())).decode())

    def get(self):
        if self.store.secret_memory.get(self.name):
            return self.store.secret_memory[self.name]
        saved = self.store.setting(self.name, "")
        if saved and os.name == "nt":
            try:
                self.store.secret_memory[self.name] = _crypt(base64.b64decode(saved), True).decode()
            except OSError:
                return ""
        return self.store.secret_memory.get(self.name,"")
