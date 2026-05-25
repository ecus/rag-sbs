"""Object storage cloud-agnóstico para PDFs originales y backups.

Tres backends:
- ``local``: filesystem montado (default dev).
- ``s3``: AWS S3.
- ``gcs``: Google Cloud Storage vía interfaz S3-compatible (gestor `boto3`
  apuntado a ``https://storage.googleapis.com``).

Misma API en los tres. Se selecciona vía env var ``OBJECT_STORE_BACKEND``.
Esto nos da portabilidad real AWS ↔ GCP sin cambiar código de aplicación.
"""

from __future__ import annotations

import io
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO

logger = logging.getLogger(__name__)


class ObjectStore(ABC):
    """Interfaz mínima para guardar/leer objetos binarios por clave."""

    @abstractmethod
    def put(self, key: str, data: bytes | IO[bytes], content_type: str | None = None) -> str:
        """Sube un objeto. Retorna la URI (ej. ``s3://bucket/key`` o ``file:///...``)."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Descarga el objeto completo."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """True si el objeto existe."""

    @abstractmethod
    def list_prefix(self, prefix: str) -> list[str]:
        """Lista keys que comienzan con prefix."""


# --------------------------------------------------------------------------
# Implementación: filesystem local
# --------------------------------------------------------------------------

class LocalObjectStore(ObjectStore):
    """Filesystem local. Útil para dev y para deploys en una sola VM (Lightsail)."""

    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        # No permitir escapar del root
        clean = key.lstrip("/").replace("..", "")
        path = self.root / clean
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put(self, key: str, data: bytes | IO[bytes], content_type: str | None = None) -> str:
        path = self._full_path(key)
        contenido = data.read() if hasattr(data, "read") else data
        path.write_bytes(contenido)
        return f"file://{path}"

    def get(self, key: str) -> bytes:
        return self._full_path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._full_path(key).exists()

    def list_prefix(self, prefix: str) -> list[str]:
        base = self._full_path(prefix.rstrip("/"))
        if not base.exists():
            return []
        if base.is_file():
            return [str(base.relative_to(self.root))]
        return [
            str(p.relative_to(self.root))
            for p in base.rglob("*")
            if p.is_file()
        ]


# --------------------------------------------------------------------------
# Implementación: S3-compatible (AWS S3 y GCS via interop)
# --------------------------------------------------------------------------

class S3CompatibleObjectStore(ObjectStore):
    """AWS S3 y Google Cloud Storage (via interop S3).

    Para AWS: deja ``endpoint_url=None`` (usa default https://s3.amazonaws.com).
    Para GCS: usar ``endpoint_url="https://storage.googleapis.com"`` con
    HMAC keys generadas en la consola de GCP.
    Para MinIO/Wasabi/cualquier otro: pasar el endpoint correspondiente.
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        # Import lazy para no requerir boto3 en dev local
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore

        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key or os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=secret_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    def put(self, key: str, data: bytes | IO[bytes], content_type: str | None = None) -> str:
        body = data if hasattr(data, "read") else io.BytesIO(data)
        extra = {"ContentType": content_type} if content_type else {}
        self._client.put_object(Bucket=self.bucket, Key=key, Body=body, **extra)
        scheme = "s3" if not self.endpoint_url else "obj"
        return f"{scheme}://{self.bucket}/{key}"

    def get(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001
            return False

    def list_prefix(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []) or []:
                keys.append(item["Key"])
        return keys


# --------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------

def get_object_store() -> ObjectStore:
    """Factory: devuelve la implementación según ``OBJECT_STORE_BACKEND``.

    Vars de entorno relevantes:
    - ``OBJECT_STORE_BACKEND``: ``local`` | ``s3`` | ``gcs`` (default: ``local``)
    - ``OBJECT_STORE_LOCAL_DIR``: dir base si backend=local (default: ``./data/objects``)
    - ``OBJECT_STORE_BUCKET``: bucket name si s3/gcs
    - ``OBJECT_STORE_REGION``: región (default: ``us-east-1``)
    - ``OBJECT_STORE_ENDPOINT_URL``: endpoint custom para gcs/minio
    - ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY``: credenciales
    """
    backend = os.getenv("OBJECT_STORE_BACKEND", "local").lower()

    if backend == "local":
        root = os.getenv("OBJECT_STORE_LOCAL_DIR", "./data/objects")
        return LocalObjectStore(root_dir=root)

    if backend in ("s3", "gcs"):
        bucket = os.getenv("OBJECT_STORE_BUCKET")
        if not bucket:
            raise ValueError(
                "OBJECT_STORE_BUCKET requerido para backend s3/gcs"
            )
        endpoint = os.getenv("OBJECT_STORE_ENDPOINT_URL")
        if backend == "gcs" and not endpoint:
            endpoint = "https://storage.googleapis.com"
        return S3CompatibleObjectStore(
            bucket=bucket,
            region=os.getenv("OBJECT_STORE_REGION", "us-east-1"),
            endpoint_url=endpoint,
        )

    raise ValueError(
        f"OBJECT_STORE_BACKEND desconocido: {backend!r}. "
        f"Valores válidos: local, s3, gcs."
    )
