variable "hcloud_token" {
  type        = string
  sensitive   = true
  description = "Hetzner Cloud API token (set via TF_VAR_hcloud_token)"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "ssh_private_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519"
}

variable "vigil_branch" {
  type    = string
  default = "feat/hetzner-infra-terraform"
}

variable "github_token" {
  type        = string
  sensitive   = true
  description = "GitHub PAT with repo scope — used by flux bootstrap to create deploy key (set via TF_VAR_github_token)"
}

variable "vigil_webhook_secret" {
  type        = string
  sensitive   = true
  description = "Bearer token for the vigil orchestrator webhook"
}

variable "llm_api_key" {
  type      = string
  sensitive = true
}

variable "llm_base_url" {
  type = string
}

variable "llm_model_name" {
  type = string
}
