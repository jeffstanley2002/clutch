variable "project_name" {
  description = "Short project name used in emulated AWS resource names."
  type        = string
  default     = "clutch"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project_name))
    error_message = "project_name must be 2-21 lowercase letters, digits, or hyphens."
  }
}

variable "environment" {
  description = "LocalStack environment label."
  type        = string
  default     = "localstack"

  validation {
    condition     = var.environment == "localstack"
    error_message = "environment must be localstack for this harness."
  }
}

variable "aws_region" {
  description = "Emulated AWS region."
  type        = string
  default     = "ap-southeast-1"
}

variable "vpc_cidr" {
  description = "CIDR for the emulated LocalStack VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "image_tag" {
  description = "Image tag referenced by emulated ECS task definitions."
  type        = string
  default     = "localstack"
}

variable "enable_emulated_ecr" {
  description = "Create LocalStack ECR repositories. Requires a LocalStack license tier that includes ECR."
  type        = bool
  default     = false
}

variable "enable_emulated_ecs" {
  description = "Create LocalStack ECS task definitions and services. Requires a LocalStack license tier that includes ECS."
  type        = bool
  default     = false
}

variable "service_desired_count" {
  description = "Emulated ECS desired count. Keep zero unless explicitly testing LocalStack ECS task execution."
  type        = number
  default     = 0

  validation {
    condition     = var.service_desired_count >= 0 && var.service_desired_count <= 1
    error_message = "service_desired_count must be zero or one for the LocalStack harness."
  }
}

variable "clutch_api_key" {
  description = "Non-production API key stored in LocalStack Secrets Manager."
  type        = string
  default     = "localstack-dev-only"
  sensitive   = true

  validation {
    condition     = length(var.clutch_api_key) >= 12
    error_message = "clutch_api_key must be at least 12 characters."
  }
}

variable "openai_model" {
  description = "Model name passed through the emulated backend task definition."
  type        = string
  default     = "gpt-5.4-mini"
}
