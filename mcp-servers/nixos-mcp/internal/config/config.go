package config

import (
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
)

type Config struct {
	SSHHosts               []string
	SSHUser                string
	SSHKeyPath             string
	MaxOutputBytesDescribe int
	MaxOutputBytesLogs     int
	SSHDialTimeout         time.Duration
	SSHDialRetries         int
	SSHDialBackoff         time.Duration
}

func Load() *Config {
	hosts := strings.Split(os.Getenv("SSH_HOSTS"), ",")
	if len(hosts) == 1 && hosts[0] == "" {
		hosts = nil
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
	}
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return fallback
}
