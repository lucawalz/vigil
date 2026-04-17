package ssh

import (
	"testing"
)

func TestValidateCommand_AllowedCommands(t *testing.T) {
	cases := []struct {
		binary string
		args   []string
	}{
		{"journalctl", []string{"-u", "k3s", "-n", "100"}},
		{"systemctl", []string{"status", "k3s"}},
		{"systemctl", []string{"is-active", "k3s"}},
		{"systemctl", []string{"is-failed", "k3s"}},
		{"free", []string{"-m"}},
		{"df", []string{"-h"}},
		{"uptime", nil},
		{"ip", []string{"addr"}},
		{"ip", []string{"route"}},
		{"ip", []string{"link"}},
		{"ss", []string{"-tlnp"}},
	}
	for _, c := range cases {
		err := validateCommand(c.binary, c.args)
		if err != nil {
			t.Errorf("validateCommand(%q, %v) = %v, want nil", c.binary, c.args, err)
		}
	}
}

func TestValidateCommand_RejectedBinaries(t *testing.T) {
	cases := []struct {
		binary string
		args   []string
	}{
		{"rm", []string{"-rf", "/"}},
		{"bash", []string{"-c", "echo pwned"}},
		{"sh", []string{"-c", "id"}},
		{"curl", []string{"http://evil.com"}},
		{"nixos-rebuild", []string{"switch"}},
		{"kubectl", []string{"delete", "pods", "--all"}},
	}
	for _, c := range cases {
		err := validateCommand(c.binary, c.args)
		if err == nil {
			t.Errorf("validateCommand(%q, %v) = nil, want error containing 'command not in allow-list'", c.binary, c.args)
			continue
		}
		if msg := err.Error(); !contains(msg, "command not in allow-list") {
			t.Errorf("validateCommand(%q, %v) = %q, want message containing 'command not in allow-list'", c.binary, c.args, msg)
		}
	}
}

func TestValidateCommand_RejectedSubcommands(t *testing.T) {
	cases := []struct {
		binary string
		args   []string
	}{
		{"systemctl", []string{"stop", "k3s"}},
		{"systemctl", []string{"restart", "k3s"}},
		{"systemctl", []string{"disable", "sshd"}},
		{"ip", []string{"flush", "dev", "eth0"}},
	}
	for _, c := range cases {
		err := validateCommand(c.binary, c.args)
		if err == nil {
			t.Errorf("validateCommand(%q, %v) = nil, want error containing 'sub-command not in allow-list'", c.binary, c.args)
			continue
		}
		if msg := err.Error(); !contains(msg, "sub-command not in allow-list") {
			t.Errorf("validateCommand(%q, %v) = %q, want message containing 'sub-command not in allow-list'", c.binary, c.args, msg)
		}
	}
}

func TestValidateCommand_ShellMetacharacters(t *testing.T) {
	cases := []struct {
		binary string
		args   []string
	}{
		{"journalctl", []string{"-u", "k3s; rm -rf /"}},
		{"journalctl", []string{"-u", "k3s | cat /etc/shadow"}},
		{"journalctl", []string{"-u", "$(whoami)"}},
		{"journalctl", []string{"-u", "`whoami`"}},
		{"free", []string{"-m & echo pwned"}},
		{"df", []string{"-h; id"}},
		{"journalctl", []string{"-u", "k3s > /tmp/exfil"}},
		{"journalctl", []string{"-u", "k3s < /dev/urandom"}},
	}
	for _, c := range cases {
		err := validateCommand(c.binary, c.args)
		if err == nil {
			t.Errorf("validateCommand(%q, %v) = nil, want error containing 'shell metacharacter'", c.binary, c.args)
			continue
		}
		if msg := err.Error(); !contains(msg, "shell metacharacter") {
			t.Errorf("validateCommand(%q, %v) = %q, want message containing 'shell metacharacter'", c.binary, c.args, msg)
		}
	}
}

// contains is a helper that checks if s contains substr.
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(substr) == 0 || containsStr(s, substr))
}

func containsStr(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
