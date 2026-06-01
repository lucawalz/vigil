package nixos

import (
	"context"
	"errors"
	"fmt"
	"net"
	"os"
	"os/user"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	gossh "golang.org/x/crypto/ssh"
)

const defaultSSHDialTimeout = 15 * time.Second

func expandTilde(path string) (string, error) {
	if !strings.HasPrefix(path, "~/") {
		return path, nil
	}
	u, err := user.Current()
	if err != nil {
		return "", fmt.Errorf("get current user: %w", err)
	}
	return filepath.Join(u.HomeDir, path[2:]), nil
}

var shellMetaRE = regexp.MustCompile(`[;&|$` + "`" + `(){}<>\n\r]`)

func validateArg(name, value string) error {
	if shellMetaRE.MatchString(value) {
		return fmt.Errorf("%s: contains disallowed shell metacharacter", name)
	}
	if strings.ContainsAny(value, " \t") {
		return fmt.Errorf("%s: contains whitespace; flag injection rejected", name)
	}
	if strings.HasPrefix(value, "-") {
		return fmt.Errorf("%s: leading dash rejected to prevent flag injection", name)
	}
	return nil
}

type NixOSClient interface {
	GetGenerations(ctx context.Context, host string) (string, error)
	StageGeneration(ctx context.Context, host string, generation int) (string, error)
	CommitGeneration(ctx context.Context, host string) (string, error)
	RebuildTest(ctx context.Context, host string) (string, error)
	GetJournal(ctx context.Context, host, unit string, lines int) (string, error)
	GetSystemdStatus(ctx context.Context, host, unit string) (string, error)
	GetSysctl(ctx context.Context, host, key string) (string, error)
	EtcdSnapshotSave(ctx context.Context, host, destPath string) (string, error)
	GetNixPath(ctx context.Context, hostname string) (string, error)
	DryBuild(ctx context.Context, host string) (string, error)
	TriggerReconcile(ctx context.Context, host string) (string, error)
}

type realNixOSClient struct {
	user         string
	signer       gossh.Signer
	allowedHosts []string
	dialTimeout  time.Duration
}

func NewRealNixOSClient(user, keyPath string, allowedHosts []string, dialTimeout time.Duration) (NixOSClient, error) {
	expanded, err := expandTilde(keyPath)
	if err != nil {
		return nil, err
	}
	keyBytes, err := os.ReadFile(expanded)
	if err != nil {
		return nil, fmt.Errorf("read SSH key %s: %w", expanded, err)
	}
	signer, err := gossh.ParsePrivateKey(keyBytes)
	if err != nil {
		return nil, fmt.Errorf("parse SSH key: %w", err)
	}
	if dialTimeout <= 0 {
		dialTimeout = defaultSSHDialTimeout
	}
	return &realNixOSClient{
		user:         user,
		signer:       signer,
		allowedHosts: allowedHosts,
		dialTimeout:  dialTimeout,
	}, nil
}

func validateHost(host string, allowed []string) error {
	if len(allowed) == 0 {
		return fmt.Errorf("SSH_HOSTS is not configured; refusing to connect")
	}
	for _, h := range allowed {
		if h == host {
			return nil
		}
	}
	return fmt.Errorf("host %q is not in SSH_HOSTS allow-list", host)
}

func (c *realNixOSClient) runSSH(ctx context.Context, host, cmd string) (string, error) {
	if strings.ContainsAny(host, ":/ \t\n\r") {
		return "", fmt.Errorf("host contains invalid character")
	}
	if err := validateHost(host, c.allowedHosts); err != nil {
		return "", err
	}
	if err := validateCommand(cmd); err != nil {
		return "", err
	}
	cfg := &gossh.ClientConfig{
		User:            c.user,
		Auth:            []gossh.AuthMethod{gossh.PublicKeys(c.signer)},
		HostKeyCallback: gossh.InsecureIgnoreHostKey(), //nolint:gosec
		Timeout:         c.dialTimeout,
	}

	dialer := net.Dialer{Timeout: c.dialTimeout}
	netConn, err := dialer.DialContext(ctx, "tcp", host+":22")
	if err != nil {
		return "", fmt.Errorf("ssh dial %s: %w", host, err)
	}
	sshConn, chans, reqs, err := gossh.NewClientConn(netConn, host+":22", cfg)
	if err != nil {
		_ = netConn.Close()
		return "", fmt.Errorf("ssh handshake %s: %w", host, err)
	}
	conn := gossh.NewClient(sshConn, chans, reqs)
	defer func() { _ = conn.Close() }()

	session, err := conn.NewSession()
	if err != nil {
		return "", fmt.Errorf("ssh session: %w", err)
	}
	defer func() { _ = session.Close() }()

	out, err := session.CombinedOutput(cmd)
	return string(out), err
}

func (c *realNixOSClient) GetGenerations(ctx context.Context, host string) (string, error) {
	return c.runSSH(ctx, host, "nix-env -p /nix/var/nix/profiles/system --list-generations")
}

func (c *realNixOSClient) StageGeneration(ctx context.Context, host string, generation int) (string, error) {
	cmd := fmt.Sprintf(
		"sudo systemctl start rollback-gate.timer && sudo nix-env --switch-generation %d -p /nix/var/nix/profiles/system && sudo /nix/var/nix/profiles/system/bin/switch-to-configuration test",
		generation,
	)
	return c.runSSH(ctx, host, cmd)
}

func (c *realNixOSClient) CommitGeneration(ctx context.Context, host string) (string, error) {
	cmd := "sudo /nix/var/nix/profiles/system/bin/switch-to-configuration boot && sudo systemctl stop rollback-gate.timer"
	return c.runSSH(ctx, host, cmd)
}

func (c *realNixOSClient) RebuildTest(ctx context.Context, host string) (string, error) {
	_, rebuildErr := c.runSSH(ctx, host, fmt.Sprintf("sudo nixos-rebuild test --flake /opt/vigil/infra/nixos#%s", host))
	exitCode := 0
	if rebuildErr != nil {
		exitCode = 1
	}

	healthGate, _ := c.runSSH(ctx, host, "systemctl is-active rollback-gate.service")
	healthGate = strings.TrimSpace(healthGate)

	k8sReady, _ := c.runSSH(ctx, host, `kubectl get node $(hostname) -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'`)
	k8sReady = strings.TrimSpace(k8sReady)

	result := fmt.Sprintf("nixos-rebuild exit: %d\nhealth-gate: %s\nk8s-node-ready: %s", exitCode, healthGate, k8sReady)
	return result, nil
}

func (c *realNixOSClient) GetJournal(ctx context.Context, host, unit string, lines int) (string, error) {
	if unit != "" {
		if err := validateArg("unit", unit); err != nil {
			return "", err
		}
		return c.runSSH(ctx, host, fmt.Sprintf("journalctl -u %s -n %d --no-pager", unit, lines))
	}
	return c.runSSH(ctx, host, fmt.Sprintf("journalctl -n %d --no-pager", lines))
}

func (c *realNixOSClient) GetSystemdStatus(ctx context.Context, host, unit string) (string, error) {
	if err := validateArg("unit", unit); err != nil {
		return "", err
	}
	out, err := c.runSSH(ctx, host, fmt.Sprintf("systemctl status %s --no-pager", unit))
	var exitErr *gossh.ExitError
	if errors.As(err, &exitErr) {
		return out, nil
	}
	return out, err
}

func (c *realNixOSClient) GetSysctl(ctx context.Context, host, key string) (string, error) {
	if err := validateArg("key", key); err != nil {
		return "", err
	}
	return c.runSSH(ctx, host, fmt.Sprintf("sysctl %s", key))
}

func (c *realNixOSClient) EtcdSnapshotSave(ctx context.Context, host, destPath string) (string, error) {
	if err := validateArg("dest_path", destPath); err != nil {
		return "", err
	}
	return c.runSSH(ctx, host, fmt.Sprintf("sudo etcdctl snapshot save %s", destPath))
}

var knownNixOSHosts = map[string]bool{
	"hetzner-master":   true,
	"hetzner-worker-1": true,
	"hetzner-worker-2": true,
	"hetzner-agent":    true,
}

func (c *realNixOSClient) GetNixPath(_ context.Context, hostname string) (string, error) {
	if err := validateArg("hostname", hostname); err != nil {
		return "", err
	}
	if !knownNixOSHosts[hostname] {
		return "", fmt.Errorf("unknown hostname: %q", hostname)
	}
	return fmt.Sprintf("infra/nixos/hosts/%s/default.nix", hostname), nil
}

func (c *realNixOSClient) DryBuild(ctx context.Context, host string) (string, error) {
	return c.runSSH(ctx, host, fmt.Sprintf("sudo nixos-rebuild dry-activate --flake /opt/vigil/infra/nixos#%s", host))
}

func (c *realNixOSClient) TriggerReconcile(ctx context.Context, host string) (string, error) {
	cmd := "systemctl start --no-block vigil-auto-reconcile.service"
	out, err := c.runSSH(ctx, host, cmd)
	if err != nil {
		return "", fmt.Errorf("trigger_reconcile: %w", err)
	}
	return fmt.Sprintf("issued: %s\nresponse: %s", cmd, out), nil
}
