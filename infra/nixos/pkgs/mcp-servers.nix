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
  kubectl-mcp = mkMcpServer { name = "kubectl-mcp"; vendorHash = "sha256-gHQqBO4nY2hMq7ohF1X8Qp33pQP6hmn5qVvcnOv+dHw="; };
  flux-mcp = mkMcpServer { name = "flux-mcp"; vendorHash = "sha256-IYVV0vwQCoyztwRlCEAzvGTrS46z49Q6kK7XwuIZtaU="; };
  nixos-mcp = mkMcpServer { name = "nixos-mcp"; vendorHash = "sha256-YKM1Eyo48MrqvrKws4YrYPN2UWtvt9HGrZQFpA7ph9g="; };
  git-mcp = mkMcpServer { name = "git-mcp"; vendorHash = "sha256-dkfPmX66Y1CVuEZUO8QjbhKRoT0bZN/YnGJlE92biIM="; nativeBuildInputs = [ pkgs.git ]; };
}
