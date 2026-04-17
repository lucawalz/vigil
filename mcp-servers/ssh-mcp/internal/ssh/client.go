package ssh

import (
	"context"
	"fmt"
	"os"
	"os/user"
	"path/filepath"
	"strings"

	gossh "golang.org/x/crypto/ssh"
)

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

type SSHClient interface {
	RunAllowedCommand(ctx context.Context, host, binary string, args []string) (string, error)
}

type realSSHClient struct {
	user   string
	signer gossh.Signer
}

func NewRealSSHClient(user, keyPath string) (SSHClient, error) {
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
	return &realSSHClient{user: user, signer: signer}, nil
}

func (c *realSSHClient) RunAllowedCommand(ctx context.Context, host, binary string, args []string) (string, error) {
	if err := validateCommand(binary, args); err != nil {
		return "", err
	}

	cfg := &gossh.ClientConfig{
		User: c.user,
		Auth: []gossh.AuthMethod{
			gossh.PublicKeys(c.signer),
		},
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

	cmd := binary
	if len(args) > 0 {
		cmd = binary + " " + strings.Join(args, " ")
	}
	out, err := session.Output(cmd)
	if err != nil {
		return "", fmt.Errorf("ssh exec %s: %w", cmd, err)
	}
	return string(out), nil
}
