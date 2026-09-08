variable "project_name" {
  description = "Short project name used in AWS resource names."
  type        = string
  default     = "clutch"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project_name))
    error_message = "project_name must be 2-21 lowercase letters, digits, or hyphens."
  }
}

variable "environment" {
  description = "Deployment environment label."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "aws_region" {
  description = "AWS region for all application resources."
  type        = string
  default     = "ap-southeast-1"
}

variable "vpc_cidr" {
  description = "CIDR for the isolated Clutch VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "allowed_ingress_cidr" {
  description = "CIDR allowed to reach the public load balancer. Narrow this when possible."
  type        = string
  default     = "0.0.0.0/0"
}

variable "budget_alert_email" {
  description = "Email that receives forecasted and actual AWS budget alerts."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.budget_alert_email))
    error_message = "budget_alert_email must be a valid email address."
  }
}

variable "monthly_budget_usd" {
  description = "Monthly AWS budget alert threshold in USD."
  type        = number
  default     = 30

  validation {
    condition     = var.monthly_budget_usd >= 5
    error_message = "monthly_budget_usd must be at least 5."
  }
}

variable "service_desired_count" {
  description = "Tasks per ECS service. Keep at zero until images and migrations are ready."
  type        = number
  default     = 0

  validation {
    condition     = var.service_desired_count >= 0 && var.service_desired_count <= 2
    error_message = "service_desired_count must be between zero and two."
  }
}

variable "image_tag" {
  description = "Immutable image tag pushed to all three ECR repositories."
  type        = string
  default     = "bootstrap"
}

variable "acm_certificate_arn" {
  description = "Optional ACM certificate ARN; when set, HTTP redirects to HTTPS."
  type        = string
  default     = null
  nullable    = true
}

variable "db_engine_version" {
  description = "Supported Amazon RDS PostgreSQL engine major/minor version."
  type        = string
  default     = "16"
}

variable "db_instance_class" {
  description = "RDS instance class for the portfolio environment."
  type        = string
  default     = "db.t4g.micro"
}

variable "redis_node_type" {
  description = "ElastiCache node type for the portfolio environment."
  type        = string
  default     = "cache.t4g.micro"
}

variable "enable_deletion_protection" {
  description = "Protect RDS from deletion; enable for production."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch application log retention."
  type        = number
  default     = 7
}

variable "openai_api_key_secret_arn" {
  description = "Optional Secrets Manager ARN holding the OpenAI API key as plaintext."
  type        = string
  default     = null
  nullable    = true
}

variable "clutch_api_key_secret_arn" {
  description = "Secrets Manager ARN holding the API key shared by Streamlit and FastAPI."
  type        = string
  default     = null
  nullable    = true
}

variable "model_per_request_usd" {
  description = "Maximum estimated OpenAI spend reserved before one provider call."
  type        = number
  default     = 0.10

  validation {
    condition     = var.model_per_request_usd > 0
    error_message = "model_per_request_usd must be positive."
  }
}

variable "model_daily_usd" {
  description = "UTC-day OpenAI spend ceiling shared through Redis."
  type        = number
  default     = 1.00

  validation {
    condition     = var.model_daily_usd > 0 && var.model_daily_usd >= var.model_per_request_usd
    error_message = "model_daily_usd must be positive and at least model_per_request_usd."
  }
}

variable "github_token_secret_arn" {
  description = "Optional Secrets Manager ARN holding a read-only GitHub token as plaintext."
  type        = string
  default     = null
  nullable    = true
}

variable "langfuse_public_key_secret_arn" {
  description = "Optional Secrets Manager ARN holding the Langfuse public key."
  type        = string
  default     = null
  nullable    = true
}

variable "langfuse_secret_key_secret_arn" {
  description = "Optional Secrets Manager ARN holding the Langfuse secret key."
  type        = string
  default     = null
  nullable    = true
}

variable "langfuse_base_url" {
  description = "Langfuse endpoint used only when both tracing key ARNs are set."
  type        = string
  default     = "https://cloud.langfuse.com"
}

variable "openai_model" {
  description = "OpenAI model used by the structured review provider."
  type        = string
  default     = "gpt-5.4-mini"
}

variable "openai_embedding_model" {
  description = "OpenAI embedding model; migrations expect 1536 dimensions."
  type        = string
  default     = "text-embedding-3-small"
}
