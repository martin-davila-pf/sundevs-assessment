import base64
import json
from unittest.mock import Mock

import pytest

import handler as app


@pytest.fixture
def deps(monkeypatch):
    cache, s3 = Mock(), Mock()
    cache.get.return_value = None
    monkeypatch.setenv("BUCKET_NAME", "test-bucket")
    monkeypatch.setattr(app, "clients", lambda: (cache, s3))
    return cache, s3


def invoke(body='{"message":"hello"}', **extra):
    return app.handler({"body": body, **extra}, None)


def test_miss_persists_before_caching_with_ttl(deps):
    cache, s3 = deps
    order = Mock()
    order.attach_mock(s3.put_object, "persist")
    order.attach_mock(cache.set, "cache")
    result = invoke()
    assert result["statusCode"] == 200
    assert result["headers"]["X-Cache"] == "MISS"
    body = json.loads(result["body"])
    assert body["object_key"].startswith("results/")
    assert body["object_key"].endswith(f"/{body['id']}.json")
    assert [c[0] for c in order.mock_calls] == ["persist", "cache"]
    assert cache.set.call_args.kwargs == {"ex": 60}
    assert s3.put_object.call_args.kwargs["Body"].decode() == result["body"]


def test_hit_skips_processing_and_persistence(deps):
    cache, s3 = deps
    cache.get.return_value = '{"cached":true}'
    result = invoke()
    assert result["headers"]["X-Cache"] == "HIT"
    assert result["body"] == '{"cached":true}'
    s3.put_object.assert_not_called()
    cache.set.assert_not_called()


def test_equivalent_json_uses_same_key(deps):
    cache, _ = deps
    invoke('{"a":1,"b":2}')
    first = cache.get.call_args
    invoke('{ "b": 2, "a": 1 }')
    assert cache.get.call_args == first


def test_base64_request(deps):
    result = invoke(base64.b64encode(b'{"message":"hello"}').decode(), isBase64Encoded=True)
    assert result["statusCode"] == 200


@pytest.mark.parametrize("body", [None, "not json", "x" * 16385, "NaN"])
def test_bad_body_returns_descriptive_500(deps, body):
    result = invoke(body)
    assert result["statusCode"] == 500
    assert result["headers"]["X-Cache"] == "MISS"
    assert "validacion de la peticion" in result["body"]


def test_s3_failure_does_not_cache(deps):
    cache, s3 = deps
    s3.put_object.side_effect = RuntimeError("secret must not leak")
    result = invoke()
    assert result["statusCode"] == 500
    assert "persistencia en S3" in result["body"]
    assert "secret" not in result["body"]
    cache.set.assert_not_called()


def test_redis_read_failure_is_500(deps):
    cache, s3 = deps
    cache.get.side_effect = ConnectionError("unreachable")
    result = invoke()
    assert result["statusCode"] == 500
    assert "consulta en la cache" in result["body"]
    s3.put_object.assert_not_called()


def test_redis_write_failure_is_500_after_persistence(deps):
    cache, s3 = deps
    cache.set.side_effect = ConnectionError("unreachable")
    result = invoke()
    assert result["statusCode"] == 500
    assert "escritura en la cache" in result["body"]
    s3.put_object.assert_called_once()
