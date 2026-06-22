variable "hcloud_token" {
  type      = string
  sensitive = true
}

variable "role" {
  type        = string
  description = "Server role: master, worker-1, worker-2, or agent"

  validation {
    condition     = contains(["master", "worker-1", "worker-2", "agent"], var.role)
    error_message = "Role must be one of: master, worker-1, worker-2, or agent."
  }
}

variable "nixos_commit_sha" {
  type        = string
  description = "Git commit SHA pinning the NixOS flake URL used by nixos-anywhere"
}

variable "nixos_hash" {
  type        = string
  description = "Git tree hash of infra/nixos/ - used as snapshot label for cache invalidation"
}

variable "ssh_private_key_file" {
  type        = string
  description = "Path to the ED25519 private key file used for both Packer SSH and nixos-anywhere"
}
