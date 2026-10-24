resource "aws_s3_bucket" "results" {
  bucket        = "${local.name}-results"
  force_destroy = true # La eliminacion borra tambien las versiones de los objetos.
}
resource "aws_s3_bucket_public_access_block" "results" {
  bucket                  = aws_s3_bucket.results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "results" {
  bucket = aws_s3_bucket.results.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_policy" "results" {
  bucket = aws_s3_bucket.results.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    {
      Sid       = "RequireTLS", Effect = "Deny", Principal = "*", Action = "s3:*",
      Resource  = [aws_s3_bucket.results.arn, "${aws_s3_bucket.results.arn}/*"],
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    },
    {
      Sid       = "OnlyProcessorObjectAccess", Effect = "Deny", Principal = "*",
      Action    = ["s3:GetObject*", "s3:PutObject*", "s3:DeleteObject*"],
      Resource  = "${aws_s3_bucket.results.arn}/*",
      Condition = { ArnNotEquals = { "aws:PrincipalArn" = aws_iam_role.lambda.arn } }
    },
    {
      Sid       = "OnlyThroughEndpoint", Effect = "Deny", Principal = "*",
      Action    = ["s3:GetObject*", "s3:PutObject*", "s3:DeleteObject*"],
      Resource  = "${aws_s3_bucket.results.arn}/*",
      Condition = { StringNotEquals = { "aws:SourceVpce" = aws_vpc_endpoint.s3.id } }
    }
  ] })
}
resource "aws_elasticache_subnet_group" "redis" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = local.name
  description                = "Cache de la prueba, con TTL fijo en la aplicacion"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = var.redis_node_type
  num_cache_clusters         = 1
  port                       = 6379
  parameter_group_name       = "default.redis7"
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis.result
  automatic_failover_enabled = false
  multi_az_enabled           = false
  snapshot_retention_limit   = 0
  apply_immediately          = true
}
