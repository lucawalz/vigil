package nixos

import (
	"context"
	"fmt"
	"os"
	"regexp"
	"strings"

	gossh "golang.org/x/crypto/ssh"
)

var shellMetaRE = regexp.MustCompile(`[;&|$` + "`" + `(){}<>\n\r]`)

func validateArg(name, value string) error {
	if shellMetaRE.MatchString(value) {
		return fmt.Errorf("%s: contains disallowed shell metacharacter", name)
	}
	return nil
}

type NixOSClient interface {
	GetGenerations(ctx context.Context, host string) (string, error)
	SwitchGeneration(ctx context.Context, host string, generation int) (string, error)
	RebuildTest(ctx context.Context, host string) (string, error)
	GetJournal(ctx context.Context, host, unit string, lines int) (string, error)
	GetSystemdStatus(ctx context.Context, host, unit string) (string, error)
	EtcdSnapshotSave(ctx context.Context, host, destPath string) (string, error)
}

type realNixOSClient struct {
	user   string
	signer gossh.Signer
}

func NewRealNixOSClient(user, keyPath string) (NixOSClient, error) {
	keyBytes, err := os.ReadFile(keyPath)
	if err != nil {
		return nil, fmt.Errorf("read SSH key %s: %w", keyPath, err)
	}
	signer, err := gossh.ParsePrivateKey(keyBytes)
	if err != nil {
		return nil, fmt.Errorf("parse SSH key: %w", err)
	}
	return &realNixOSClient{user: user, signer: signer}, nil
}

func (c *realNixOSClient) runSSH(host, cmd string) (string, error) {
	cfg := &gossh.ClientConfig{
		User: c.user,
		Auth: []gossh.AuthMethod{gossh.PublicKeys(c.signer)},
		HostKeyCallback: gossh.InsecureIgnoreHostKey(), //nolint:gosec
	}
	conn, err := gossh.Dial("tcp", host+":22", cfg)
	if err != nil {
		return "", fmt.Errorf("ssh dial %s: %w", host, err)
	}
	defer conn.Close()

	session, err := conn.NewSession()
	if err != nil {
		return "", fmt.Errorf("ssh session: %w", err)
	}
	defer session.Close()

	out, err := session.CombinedOutput(cmd)
	return string(out), err
}

func (c *realNixOSClient) GetGenerations(_ context.Context, host string) (string, error) {
	return c.runSSH(host, "nixos-rebuild list-generations")
}

func (c *realNixOSClient) SwitchGeneration(_ context.Context, host string, generation int) (string, error) {
	cmd := fmt.Sprintf(
		"sudo nix-env --switch-generation %d -p /nix/var/nix/profiles/system && sudo /nix/var/nix/profiles/system/bin/switch-to-configuration switch",
		generation,
	)
	return c.runSSH(host, cmd)
}

func (c *realNixOSClient) RebuildTest(_ context.Context, host string) (string, error) {
	_, rebuildErr := c.runSSH(host, "sudo nixos-rebuild test")
	exitCode := 0
	if rebuildErr != nil {
		exitCode = 1
	}

	healthGate, _ := c.runSSH(host, "systemctl is-active rollback-gate.service")
	healthGate = strings.TrimSpace(healthGate)

	k8sReady, _ := c.runSSH(host, `kubectl get node $(hostname) -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'`)
	k8sReady = strings.TrimSpace(k8sReady)

	result := fmt.Sprintf("nixos-rebuild exit: %d\nhealth-gate: %s\nk8s-node-ready: %s", exitCode, healthGate, k8sReady)
	return result, nil
}

func (c *realNixOSClient) GetJournal(_ context.Context, host, unit string, lines int) (string, error) {
	if err := validateArg("unit", unit); err != nil {
		return "", err
	}
	return c.runSSH(host, fmt.Sprintf("journalctl -u %s -n %d --no-pager", unit, lines))
}

func (c *realNixOSClient) GetSystemdStatus(_ context.Context, host, unit string) (string, error) {
	if err := validateArg("unit", unit); err != nil {
		return "", err
	}
	return c.runSSH(host, fmt.Sprintf("systemctl status %s --no-pager", unit))
}

func (c *realNixOSClient) EtcdSnapshotSave(_ context.Context, host, destPath string) (string, error) {
	if err := validateArg("dest_path", destPath); err != nil {
		return "", err
	}
	return c.runSSH(host, fmt.Sprintf("sudo etcdctl snapshot save %s", destPath))
}
