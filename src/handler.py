"""Procesador con cache: primero persiste el resultado, despues lo cachea."""

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

import boto3
import redis
from botocore.config import Config

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)
TTL_SECONDS = 60
_cache = None
_s3 = None


def clients():
    global _cache, _s3
    if _cache is None:
        _cache = redis.Redis(
            host=os.environ["REDIS_HOST"],
            port=6379,
            password=os.environ["REDIS_TOKEN"],
            ssl=True,
            ssl_cert_reqs="required",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            config=Config(
                connect_timeout=2,
                read_timeout=2,
                retries={"total_max_attempts": 1},
            ),
        )
    return _cache, _s3


def response(status, body, cache_status):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "X-Cache": cache_status},
        "body": body,
    }


def handler(event, context):
    stage = "validacion de la peticion"
    try:
        body = event.get("body")
        if not isinstance(body, str) or len(body) > 16384:
            raise ValueError("Se esperaba un cuerpo JSON de 16 KiB como maximo")
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body, validate=True).decode("utf-8")
        payload = json.loads(body)
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        key = f"process:{digest}"
        stage = "conexion con la cache"
        cache, s3 = clients()
        stage = "consulta en la cache"
        cached = cache.get(key)
        if cached is not None:
            LOG.info("cache=ACIERTO id=%s", digest)
            return response(200, cached, "HIT")
        now = datetime.now(timezone.utc)
        object_key = f"results/{now:%Y-%m-%d}/{digest}.json"
        result = json.dumps(
            {
                "id": digest,
                "sha256": digest,
                "input": payload,
                "processed_at": now.isoformat(),
                "object_key": object_key,
            },
            ensure_ascii=False,
            allow_nan=False,
        )
        stage = "persistencia en S3"
        s3.put_object(
            Bucket=os.environ["BUCKET_NAME"],
            Key=object_key,
            Body=result.encode("utf-8"),
            ContentType="application/json",
        )
        stage = "escritura en la cache"
        cache.set(key, result, ex=TTL_SECONDS)
        LOG.info("cache=FALLO id=%s", digest)
        return response(200, result, "MISS")
    except Exception:
        LOG.exception("Fallo al procesar en: %s", stage)
        # Se indica el paso que fallo, sin exponer credenciales ni detalles del SDK.
        return response(500, json.dumps({"error": f"Fallo al procesar en: {stage}"}), "MISS")
