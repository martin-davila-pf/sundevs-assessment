resource "aws_iam_role" "lambda" {
  name = "${local.name}-lambda"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 1
}
resource "aws_iam_role_policy" "lambda" {
  role = aws_iam_role.lambda.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:PutObject"], Resource = "${aws_s3_bucket.results.arn}/results/*" },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.lambda.arn}:*" },
    {
      Effect   = "Allow",
      Action   = ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DescribeSubnets", "ec2:DeleteNetworkInterface", "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses"],
      Resource = "*"
    },
    {
      Sid      = "DenyENIChangesFromFunctionCode", Effect = "Deny",
      Action   = ["ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface", "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses"],
      Resource = "*", Condition = { ArnEquals = { "lambda:SourceFunctionArn" = "arn:aws:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:${local.name}" } }
    }
  ] })
}
data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/build/package"
  output_path = "${path.module}/build/lambda.zip"
}
resource "aws_lambda_function" "processor" {
  function_name    = local.name
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 10
  memory_size      = 128
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.results.id
      REDIS_HOST  = aws_elasticache_replication_group.redis.primary_endpoint_address
      REDIS_TOKEN = random_password.redis.result
    }
  }
  depends_on = [aws_iam_role_policy.lambda, aws_s3_bucket_policy.results, aws_s3_bucket_versioning.results]
}
resource "aws_apigatewayv2_api" "api" {
  name          = local.name
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins  = ["*"]
    allow_methods  = ["POST", "OPTIONS"]
    allow_headers  = ["content-type"]
    expose_headers = ["X-Cache"]
    max_age        = 300
  }
}
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.processor.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 12000
}
resource "aws_apigatewayv2_route" "process" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /process"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = 1
}
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = 1
    throttling_burst_limit = 2
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format          = jsonencode({ requestId = "$context.requestId", routeKey = "$context.routeKey", status = "$context.status", responseLength = "$context.responseLength", integrationError = "$context.integrationErrorMessage" })
  }
}
resource "aws_lambda_permission" "api" {
  statement_id  = "AllowProcessFromHTTPAPI"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/POST/process"
}
