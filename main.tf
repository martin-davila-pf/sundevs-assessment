terraform {
  required_version = ">= 1.9, < 2.0"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.7" }
    random  = { source = "hashicorp/random", version = "~> 3.7" }
  }
}
provider "aws" {
  region = var.region
  default_tags { tags = { Project = var.project, ManagedBy = "Terraform" } }
}
variable "region" { default = "us-east-1" }
variable "project" { default = "sre-assessment" }
variable "vpc_cidr" { default = "10.42.0.0/16" }
variable "redis_node_type" { default = "cache.t3.micro" }
data "aws_availability_zones" "available" { state = "available" }
data "aws_caller_identity" "current" {}
resource "random_id" "suffix" { byte_length = 4 }
resource "random_password" "redis" {
  length  = 32
  special = false
}
locals {
  name = "${var.project}-${random_id.suffix.hex}"
  azs  = slice(data.aws_availability_zones.available.names, 0, 2)
}
output "api_url" { value = "${aws_apigatewayv2_api.api.api_endpoint}/process" }
output "bucket_name" { value = aws_s3_bucket.results.id }
output "function_name" { value = aws_lambda_function.processor.function_name }
output "region" { value = var.region }
