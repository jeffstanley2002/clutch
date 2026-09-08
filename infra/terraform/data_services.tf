resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
  tags       = { Name = local.name }
}

resource "aws_db_instance" "main" {
  identifier = local.name

  allocated_storage           = 20
  max_allocated_storage       = 50
  storage_type                = "gp3"
  storage_encrypted           = true
  engine                      = "postgres"
  engine_version              = var.db_engine_version
  instance_class              = var.db_instance_class
  db_name                     = "clutch"
  username                    = "clutch"
  manage_master_user_password = true
  port                        = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period = var.environment == "production" ? 7 : 1
  deletion_protection     = var.enable_deletion_protection
  skip_final_snapshot     = var.environment != "production"
  final_snapshot_identifier = (
    var.environment == "production" ? "${local.name}-final" : null
  )
  apply_immediately = var.environment == "staging"

  depends_on = [aws_budgets_budget.monthly]
}

resource "aws_elasticache_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = local.name
  description          = "Clutch derived-data cache"

  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = var.redis_node_type
  port                       = 6379
  num_cache_clusters         = 1
  parameter_group_name       = "default.redis7"
  automatic_failover_enabled = false
  multi_az_enabled           = false

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  apply_immediately          = var.environment == "staging"

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  depends_on = [aws_budgets_budget.monthly]
}
