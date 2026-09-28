terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-central-1" # Francoforte
}

# ==========================================
# 1. DATABASE NoSQL: DYNAMODB
# ==========================================
resource "aws_dynamodb_table" "tournaments" {
  name           = "Tournaments"
  billing_mode   = "PAY_PER_REQUEST" # Paghi solo per le richieste effettive
  hash_key       = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = {
    Project = "swiss-tournament"
  }
}

# ==========================================
# 2. DATABASE RELAZIONALE: RDS POSTGRESQL
# ==========================================
data "aws_vpc" "default" {
  default = true
}

resource "aws_security_group" "rds_sg" {
  name        = "rds-public-sg"
  description = "Allow inbound PostgreSQL traffic"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier             = "player-db-cloud"
  allocated_storage      = 20
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t3.micro" # Tier gratuito AWS
  db_name                = "playersdb"
  username               = "dbadmin"
  password               = "password123" 
  skip_final_snapshot    = true
  publicly_accessible    = true # Per testare dal tuo PC
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  tags = {
    Project = "swiss-tournament"
  }
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.tournaments.name
}