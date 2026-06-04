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
  default = "chore/eval-cluster-baseline"
}

variable "github_token" {
  type        = string
  sensitive   = true
  description = "GitHub PAT with repo scope — used by flux bootstrap to create deploy key (set via TF_VAR_github_token)"
}

variable "ollama_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "ollama_base_url" {
  type    = string
  default = ""
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "llm_model_name" {
  type = string
}

variable "group_name" {
  type        = string
  description = "Scenario group name (cross|k8s|os|misc) — scopes Hetzner resource names so 4 stacks can coexist on one account"

  validation {
    condition     = contains(["cross", "k8s", "os", "misc"], var.group_name)
    error_message = "group_name must be one of: cross, k8s, os, misc."
  }
}

variable "run_id" {
  type        = string
  description = "CI run identifier — appended to the SSH key name so parallel runs never collide on fingerprint"
  default     = "local"
}

variable "operator_ssh_pubkey" {
  type        = string
  sensitive   = true
  default     = ""
  description = "Operator's personal public SSH key injected into all servers for debugging access"
}
