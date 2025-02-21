##
# From env vars
##
variable "project_name" { }
variable "aws_access_key" { }
variable "aws_secret_key" { }
variable "github_user" { }
variable "github_token" { }

##
# Local config
##
variable "i_type" {
  type    = string
  default = "t3a.medium"
}
variable "i_region" {
  type    = string
  default = "eu-south-1"
}

##
# Create key pairs
##
resource "aws_key_pair" "myseckey-crypto" {
  key_name   = "key-${var.project_name}"
  public_key = file("${abspath(path.cwd)}/key-${var.project_name}.pub")
}

##
# Configure provider
##
provider "aws" {
  access_key = "${var.aws_access_key}"
  secret_key = "${var.aws_secret_key}"
  region     = "${var.i_region}"
}

data "aws_subnet" "default" {
  filter {
    name   = "availability-zone"
    values = ["${var.i_region}a"]
  }
}

output "default_subnet_id" {
  value = data.aws_subnet.default.id
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners = ["099720109477"]  #(Official Ubuntu AMI Owner)
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "aws_security_group" "web_sg" {
  name        = "web-server-sg-breakeven"
  description = "Allow HTTP, HTTPS, and SSH access"

  # Allow HTTP (80) from anywhere
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Allows anyone to access HTTP
  }

  # Allow HTTPS (443) from anywhere
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Allows anyone to access HTTPS
  }

  # Allow SSH (22) from your IP only (Update this with your real IP)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Allows anyone to access SSH
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "project-bot-crypto" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "${var.i_type}"
  subnet_id                   = data.aws_subnet.default.id
  associate_public_ip_address = true
  key_name                    = "key-${var.project_name}"
  security_groups = [
    aws_security_group.web_sg.id
  ]
  tags = {
    Name = "bot-${var.project_name}"
  }
  ebs_block_device {
    device_name = "/dev/sda1"
    volume_size = 32
  }
  user_data = <<EOF
#!/bin/bash

# Installs git
sudo apt update && sudo apt install git -y

# Clone repo
cd /home/ubuntu
git clone https://${var.github_user}:${var.github_token}@github.com/IgnacioGoldman/freqtrade.git

sudo chown -R $(whoami) .

cd freqtrade/
sudo chmod +x ./setup.sh
./setup.sh -i
source ./.venv/bin/activate
# freqtrade trade --config user_data/config.json --strategy SampleStrategy

EOF

}

output "ec2instance" {
  value = aws_instance.project-bot-crypto.public_ip
}
