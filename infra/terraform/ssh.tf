resource "hcloud_ssh_key" "operator" {
  name       = "vigil-operator"
  public_key = file(var.ssh_public_key_path)
}
