package nixos

import (
	"strings"
	"testing"
)

func TestValidateCommandAllowsEnumeratedCommands(t *testing.T) {
	legitimate := []string{
		"nix-env -p /nix/var/nix/profiles/system --list-generations",
		"sudo systemctl start rollback-gate.timer && sudo nix-env --switch-generation 42 -p /nix/var/nix/profiles/system && sudo /nix/var/nix/profiles/system/bin/switch-to-configuration test && sudo systemctl restart systemd-sysctl",
		"sudo systemctl restart systemd-sysctl",
		"sudo /nix/var/nix/profiles/system/bin/switch-to-configuration boot && sudo systemctl stop rollback-gate.timer",
		"sudo /nix/var/nix/profiles/system/bin/switch-to-configuration test",
		"sudo /nix/var/nix/profiles/system/bin/switch-to-configuration boot",
		"sudo systemctl stop rollback-gate.timer",
		"sudo nixos-rebuild test --flake /opt/vigil/infra/nixos#hetzner-master",
		"systemctl is-active rollback-gate.service",
		`kubectl get node $(hostname) -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'`,
		"journalctl -u kubelet.service -n 50 --no-pager",
		"journalctl -n 100 --no-pager",
		"systemctl status kubelet.service --no-pager",
		"sudo etcdctl snapshot save /var/backups/etcd.db",
		"sudo nixos-rebuild dry-activate --flake /opt/vigil/infra/nixos#hetzner-worker-1",
		"systemctl start --no-block vigil-auto-reconcile.service",
	}
	for _, cmd := range legitimate {
		if err := validateCommand(cmd); err != nil {
			t.Errorf("legitimate command rejected: %q: %v", cmd, err)
		}
	}
}

func TestValidateCommandRejectsInjection(t *testing.T) {
	rejected := []string{
		"rm -rf /",
		"sudo etcdctl snapshot save /tmp/x && rm -rf /",
		"systemctl restart sshd.service",
		"sudo systemctl restart kubelet.service",
		"sudo systemctl restart",
		"kubectl delete node hetzner-master",
		"sudo /nix/var/nix/profiles/system/bin/switch-to-configuration switch",
		"curl http://evil",
	}
	for _, cmd := range rejected {
		if err := validateCommand(cmd); err == nil {
			t.Errorf("expected rejection for %q", cmd)
		}
	}
}

func TestStageGenerationCommandReappliesSysctls(t *testing.T) {
	cmd := stageGenerationCommand(42)
	if !strings.Contains(cmd, "systemctl restart systemd-sysctl") {
		t.Errorf("staged command missing sysctl reapply step: %q", cmd)
	}
	if err := validateCommand(cmd); err != nil {
		t.Errorf("staged command rejected by allow-list: %v", err)
	}
}

func TestValidateArgRejectsFlagInjection(t *testing.T) {
	cases := []string{
		"unit --vacuum-time=1s",
		"-rf",
		"a b",
	}
	for _, value := range cases {
		if err := validateArg("unit", value); err == nil {
			t.Errorf("expected validateArg rejection for %q", value)
		}
	}
}

func TestGetSysctlHandler_InvalidKey(t *testing.T) {
	const metachar = ";"
	err := validateArg("key", "vm.swappiness; echo x")
	if err == nil {
		t.Fatal("expected validateArg rejection for key containing a shell metacharacter")
	}
	if !strings.Contains(err.Error(), "metacharacter") {
		t.Errorf("expected error mentioning the metacharacter %q, got: %v", metachar, err)
	}
}

func TestValidateArgAllowsPlainValues(t *testing.T) {
	for _, value := range []string{"kubelet.service", "/var/backups/etcd.db", "hetzner-master"} {
		if err := validateArg("unit", value); err != nil {
			t.Errorf("plain value rejected: %q: %v", value, err)
		}
	}
}
