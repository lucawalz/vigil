resource "hcloud_ssh_key" "operator" {
  name       = "vigil-operator-${var.group_name}-${var.run_id}"
  public_key = trimspace(file(var.ssh_public_key_path))
}
