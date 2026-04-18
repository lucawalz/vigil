variable "hcloud_token" {
  type        = string
  sensitive   = true
  description = "Hetzner Cloud API token (set via TF_VAR_hcloud_token)"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "sops_age_key_path" {
  type        = string
  default     = "~/.config/sops/age/keys.txt"
  description = "Local file path to SOPS age private key (set via TF_VAR_sops_age_key_path); read by inject-secrets.sh, never written to state"
}
