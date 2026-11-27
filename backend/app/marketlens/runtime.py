import os
import re

from google.auth.credentials import AnonymousCredentials

from app.core.firebase import FirebaseRuntime
from app.marketlens.settings import MarketLensSettings


def marketlens_runtime(settings: MarketLensSettings) -> FirebaseRuntime:
    hosts = [os.getenv(name) for name in ("FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST")]
    if not any(hosts):
        return FirebaseRuntime(settings)

    if not settings.firebase_project_id.startswith("demo-marketlens-"):
        raise ValueError("Firebase emulators require a demo-marketlens- project")
    for host in hosts:
        match = re.fullmatch(r"127\.0\.0\.1:([0-9]{1,5})", host or "")
        if match is None or not 1 <= int(match[1]) <= 65535:
            raise ValueError("Both Firebase emulators must use explicit IPv4 loopback ports")
    if settings.firebase_credentials_path or settings.firebase_storage_bucket:
        raise ValueError("Firebase emulator mode cannot use a service account file or Storage")
    return FirebaseRuntime(settings, credential=AnonymousCredentials())
