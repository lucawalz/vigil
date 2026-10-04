package nixos

import (
	"context"
	"reflect"
	"testing"
)

func TestRebuildCommandAcceptsHetznerAndLabAttributes(t *testing.T) {
	tests := []struct {
		action string
		raw    string
		want   string
	}{
		{action: "test", raw: "vigil-worker-1", want: "sudo nixos-rebuild test --flake /opt/vigil/infra/nixos#vigil-worker-1"},
		{action: "dry-activate", raw: "vigil-worker-1-lab-aarch64", want: "sudo nixos-rebuild dry-activate --flake /opt/vigil/infra/nixos#vigil-worker-1-lab-aarch64"},
	}
	for _, tt := range tests {
		t.Run(tt.raw, func(t *testing.T) {
			got, err := rebuildCommand(tt.action, tt.raw)
			if err != nil || got != tt.want {
				t.Fatalf("rebuildCommand(%q, %q) = %q, %v; want %q", tt.action, tt.raw, got, err, tt.want)
			}
			if err := validateCommand(got); err != nil {
				t.Errorf("command rejected by allow-list: %v", err)
			}
		})
	}
}

func TestRebuildCommandRejectsInvalidAttribute(t *testing.T) {
	for _, raw := range []string{"", "Vigil-Worker-1", "vigil-worker-1;rm -rf /", "$(id)", "../vigil", "vigil worker", "vigil_worker", "#vigil"} {
		if got, err := rebuildCommand("test", raw); err == nil {
			t.Errorf("expected rejection for %q, got %q", raw, got)
		}
	}
}

func TestRebuildCommandTrimsOnlyTrailingWhitespace(t *testing.T) {
	if _, err := rebuildCommand("test", "vigil-worker-1\n"); err != nil {
		t.Fatalf("cat output with a trailing newline rejected: %v", err)
	}
	if got, err := rebuildCommand("test", "vigil-worker-1\nsudo reboot"); err == nil {
		t.Fatalf("embedded newline accepted: %q", got)
	}
}

func TestReadFlakeAttrCommandIsTheOnlyAllowedCat(t *testing.T) {
	if err := validateCommand(readFlakeAttrCommand); err != nil {
		t.Fatalf("flake-attr read rejected: %v", err)
	}
	for _, cmd := range []string{"cat /etc/shadow", "cat", "sudo cat /root/.ssh/id_ed25519", "cat /etc/vigil/flake-attr /etc/shadow"} {
		if err := validateCommand(cmd); err == nil {
			t.Errorf("expected rejection for %q", cmd)
		}
	}
}

type scriptedRunner struct {
	attr  string
	calls []string
}

func (s *scriptedRunner) run(_ context.Context, _, cmd string) (string, error) {
	s.calls = append(s.calls, cmd)
	if cmd == readFlakeAttrCommand {
		return s.attr, nil
	}
	return "", nil
}

func TestRebuildPathsReadTheFlakeAttrBeforeRebuilding(t *testing.T) {
	tests := []struct {
		name string
		call func(c *realNixOSClient) error
		want string
	}{
		{
			name: "RebuildTest",
			call: func(c *realNixOSClient) error {
				_, err := c.RebuildTest(context.Background(), "vigil-worker-1")
				return err
			},
			want: "sudo nixos-rebuild test --flake /opt/vigil/infra/nixos#vigil-worker-1",
		},
		{
			name: "DryBuild",
			call: func(c *realNixOSClient) error {
				_, err := c.DryBuild(context.Background(), "vigil-worker-1")
				return err
			},
			want: "sudo nixos-rebuild dry-activate --flake /opt/vigil/infra/nixos#vigil-worker-1",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name+" rebuilds the validated attribute", func(t *testing.T) {
			runner := &scriptedRunner{attr: "vigil-worker-1\n"}
			if err := tt.call(&realNixOSClient{runCommand: runner.run}); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(runner.calls) < 2 || runner.calls[0] != readFlakeAttrCommand || runner.calls[1] != tt.want {
				t.Fatalf("calls = %q; want %q first, then %q", runner.calls, readFlakeAttrCommand, tt.want)
			}
		})
		t.Run(tt.name+" sends no rebuild for an invalid attribute", func(t *testing.T) {
			runner := &scriptedRunner{attr: "vigil-worker-1;sudo reboot"}
			if err := tt.call(&realNixOSClient{runCommand: runner.run}); err == nil {
				t.Fatal("expected an invalid attribute error")
			}
			if !reflect.DeepEqual(runner.calls, []string{readFlakeAttrCommand}) {
				t.Fatalf("calls = %q; want only the attribute read", runner.calls)
			}
		})
	}
}
