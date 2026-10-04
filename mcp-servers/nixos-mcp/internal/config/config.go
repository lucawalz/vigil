package config

import (
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	MaxOutputBytesDescribe = 4096
	MaxOutputBytesLogs     = 2048
	SSHDialTimeoutSeconds  = 15
	SSHDialRetries         = 3
	SSHDialBackoffMs       = 500
	defaultSSHPort         = "22"
	forwardHost            = "127.0.0.1"
	minPort                = 1
	maxPort                = 65535
)

type SSHHost struct {
	Name string
	Addr string
}

type Config struct {
	SSHHosts               []SSHHost
	SSHUser                string
	SSHKeyPath             string
	MaxOutputBytesDescribe int
	MaxOutputBytesLogs     int
	SSHDialTimeout         time.Duration
	SSHDialRetries         int
	SSHDialBackoff         time.Duration
}

func ParseSSHHosts(raw string) ([]SSHHost, error) {
	if strings.TrimSpace(raw) == "" {
		return nil, nil
	}
	seen := map[string]bool{}
	var hosts []SSHHost
	for _, entry := range strings.Split(raw, ",") {
		entry = strings.TrimSpace(entry)
		name, port, hasPort := strings.Cut(entry, ":")
		if name == "" {
			return nil, fmt.Errorf("SSH_HOSTS entry %q has no host name", entry)
		}
		if seen[name] {
			return nil, fmt.Errorf("SSH_HOSTS lists %q more than once", name)
		}
		seen[name] = true
		addr := net.JoinHostPort(name, defaultSSHPort)
		if hasPort {
			n, err := strconv.Atoi(port)
			if err != nil || n < minPort || n > maxPort {
				return nil, fmt.Errorf("SSH_HOSTS entry %q has an invalid port", entry)
			}
			addr = net.JoinHostPort(forwardHost, port)
		}
		hosts = append(hosts, SSHHost{Name: name, Addr: addr})
	}
	return hosts, nil
}

func Load() (*Config, error) {
	hosts, err := ParseSSHHosts(os.Getenv("SSH_HOSTS"))
	if err != nil {
		return nil, err
	}
	user := os.Getenv("SSH_USER")
	if user == "" {
		user = "vigil-agent"
	}
	keyPath := os.Getenv("SSH_KEY_PATH")
	if keyPath == "" {
		keyPath = "~/.ssh/id_ed25519"
	}
	return &Config{
		SSHHosts:               hosts,
		SSHUser:                user,
		SSHKeyPath:             keyPath,
		MaxOutputBytesDescribe: envInt("MAX_OUTPUT_BYTES_DESCRIBE", MaxOutputBytesDescribe),
		MaxOutputBytesLogs:     envInt("MAX_OUTPUT_BYTES_LOGS", MaxOutputBytesLogs),
		SSHDialTimeout:         time.Duration(envInt("SSH_DIAL_TIMEOUT_SECONDS", SSHDialTimeoutSeconds)) * time.Second,
		SSHDialRetries:         envInt("SSH_DIAL_RETRIES", SSHDialRetries),
		SSHDialBackoff:         time.Duration(envInt("SSH_DIAL_BACKOFF_MS", SSHDialBackoffMs)) * time.Millisecond,
	}, nil
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return fallback
}
