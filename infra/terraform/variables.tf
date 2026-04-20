variable "hcloud_token" {
  type        = string
  sensitive   = true
  description = "Hetzner Cloud API token (set via TF_VAR_hcloud_token)"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "vigil_branch" {
  type    = string
  default = "feat/hetzner-infra-terraform"
}
