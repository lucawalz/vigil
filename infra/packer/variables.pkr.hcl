variable "hcloud_token" {
  type      = string
  sensitive = true
}

variable "role" {
  type        = string
  description = "Server role: control-plane-1, worker-1, worker-2, or agent"

  validation {
    condition     = contains(["control-plane-1", "worker-1", "worker-2", "agent"], var.role)
    error_message = "Role must be one of: control-plane-1, worker-1, worker-2, or agent."
  }
}

variable "nixos_commit_sha" {
  type        = string
  description = "Git commit SHA pinning the NixOS flake URL used by nixos-anywhere"
}

variable "github_repository" {
  type        = string
  description = "GitHub repository (owner/name) that holds the NixOS flake"

  validation {
    condition = (
      can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository)) &&
      length(setintersection(split("/", var.github_repository), [".", ".."])) == 0
    )
    error_message = "The github_repository must have the form owner/name, without . or .. segments."
  }
}

variable "nixos_hash" {
  type        = string
  description = "Git tree hash of infra/nixos/ - used as snapshot label for cache invalidation"
}

variable "ssh_private_key_file" {
  type        = string
  description = "Path to the ED25519 private key file used for both Packer SSH and nixos-anywhere"
}

variable "campaign_run_id" {
  type        = string
  description = "Run whose vigil-run label the snapshot and the build server carry"
}
