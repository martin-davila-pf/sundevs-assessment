"""Registra las respuestas HTTP MISS/HIT reales y confirma la clave guardada en S3."""

import argparse
import json
import pathlib
import time
import urllib.request
import uuid
from datetime import datetime, timezone

import boto3

parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True)
parser.add_argument("--bucket", required=True)
parser.add_argument("--profile")
parser.add_argument("--region", default="us-east-1")
parser.add_argument(
    "--output-dir",
    type=pathlib.Path,
    default=pathlib.Path(__file__).resolve().parents[1] / "evidence",
)
args = parser.parse_args()
out = args.output_dir
out.mkdir(parents=True, exist_ok=True)
payload = json.dumps({"message": "prueba SRE", "verification_id": str(uuid.uuid4())})
records = []
for expected in ("MISS", "HIT"):
    request = urllib.request.Request(
        args.url, data=payload.encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=20) as resp:
        body = resp.read().decode()
        headers = {
            k: v
            for k, v in resp.headers.items()
            if k.lower() in {"x-cache", "content-type", "date", "apigw-requestid"}
        }
        actual = resp.headers.get("X-Cache")
        assert resp.status == 200 and actual == expected, (resp.status, actual, body)
        records.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": "POST",
                "path": "/process",
                "request_body": payload,
                "status": resp.status,
                "headers": headers,
                "response_body": json.loads(body),
            }
        )
    time.sleep(1.2)
assert records[0]["response_body"] == records[1]["response_body"]
key = records[0]["response_body"]["object_key"]
s3 = boto3.Session(profile_name=args.profile, region_name=args.region).client("s3")
listing = s3.list_objects_v2(Bucket=args.bucket, Prefix=key)
objects = [
    {"Key": obj["Key"], "Size": obj["Size"], "LastModified": obj["LastModified"].isoformat()}
    for obj in listing.get("Contents", [])
    if obj["Key"] == key
]
assert len(objects) == 1 and objects[0]["Size"] > 0, objects
(out / "requests.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
(out / "s3-object.json").write_text(
    json.dumps({"objects": objects}, indent=2) + "\n", encoding="utf-8"
)
print("Comprobado: HTTP 200 FALLO -> HTTP 200 ACIERTO; resultados identicos; clave guardada en S3.")
print(key)
