from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _input_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _protect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("本机凭据加密仅支持 Windows。")
    source, source_buffer = _input_blob(data)
    protected = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    result = crypt32.CryptProtectData(
        ctypes.byref(source),
        "课表导出器本机凭据",
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(protected),
    )
    del source_buffer
    if not result:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(protected.pbData, protected.cbData)
    finally:
        kernel32.LocalFree(protected.pbData)


def _unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("本机凭据解密仅支持 Windows。")
    source, source_buffer = _input_blob(data)
    plain = _DataBlob()
    description = wintypes.LPWSTR()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    result = crypt32.CryptUnprotectData(
        ctypes.byref(source),
        ctypes.byref(description),
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(plain),
    )
    del source_buffer
    if not result:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(plain.pbData, plain.cbData)
    finally:
        kernel32.LocalFree(plain.pbData)
        if description:
            kernel32.LocalFree(description)


class CredentialStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, username: str, vpn_password: str, academic_password: str) -> None:
        payload = {
            "version": 1,
            "username": username,
            "vpnPassword": vpn_password,
            "academicPassword": academic_password,
        }
        plain = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        envelope = {
            "version": 1,
            "protected": base64.b64encode(_protect(plain)).decode("ascii"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(envelope, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def load(self) -> dict | None:
        if not self.path.is_file():
            return None
        try:
            envelope = json.loads(self.path.read_text(encoding="utf-8"))
            protected = base64.b64decode(envelope["protected"], validate=True)
            payload = json.loads(_unprotect(protected).decode("utf-8"))
        except Exception as error:
            raise RuntimeError(
                "本机保存的登录信息无法解密，请在界面中重新输入并保存。"
            ) from error
        username = str(payload.get("username") or "").strip()
        vpn_password = str(payload.get("vpnPassword") or "")
        academic_password = str(payload.get("academicPassword") or "")
        if not username or not vpn_password or not academic_password:
            return None
        return {
            "username": username,
            "vpnPassword": vpn_password,
            "academicPassword": academic_password,
        }

    def metadata(self) -> dict:
        saved = self.load()
        if not saved:
            return {"saved": False, "maskedUsername": ""}
        username = saved["username"]
        visible = username[-4:] if len(username) > 4 else username[-2:]
        return {
            "saved": True,
            "maskedUsername": "•" * max(2, len(username) - len(visible)) + visible,
        }

    def clear(self) -> None:
        if self.path.is_file():
            self.save("", "", "")