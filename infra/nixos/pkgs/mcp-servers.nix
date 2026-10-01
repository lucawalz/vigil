{ pkgs, self }:
let
  repoRoot = builtins.dirOf (builtins.dirOf (toString self));
  mkMcpServer = { name, vendorHash, nativeBuildInputs ? [ ] }: pkgs.buildGoModule {
    pname = name;
    version = "0.0.1";
    src = builtins.path { inherit name; path = "${repoRoot}/mcp-servers/${name}"; };
    inherit vendorHash nativeBuildInputs;
    env.CGO_ENABLED = "0";
  };
in
{
  kubectl-mcp = mkMcpServer { name = "kubectl-mcp"; vendorHash = "sha256-KocuKzTe+pLkcyvKvbnCoijiqtHsoO8P5wRMmNkG3oc="; };
  flux-mcp = mkMcpServer { name = "flux-mcp"; vendorHash = "sha256-sEf8VBbS4XThS+xobo5Od74uayJApNt9l3oX71p0U1k="; };
  nixos-mcp = mkMcpServer { name = "nixos-mcp"; vendorHash = "sha256-YKM1Eyo48MrqvrKws4YrYPN2UWtvt9HGrZQFpA7ph9g="; };
  git-mcp = mkMcpServer { name = "git-mcp"; vendorHash = "sha256-d1ysWqpEehizALW5agbtXZuIS4zdP+n+Zj38mNLxUdY="; nativeBuildInputs = [ pkgs.git ]; };
}
