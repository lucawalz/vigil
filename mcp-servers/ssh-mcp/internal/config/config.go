package config

import (
	"os"
	"strconv"
	"strings"
)

const (
	MaxOutputBytesDescribe   = 4096
	MaxOutputBytesLogs       = 2048
	MaxOutputBytesPrometheus = 10240
)

// Config holds runtime configuration for ssh-mcp loaded from environment variables.
type Config struct {
	SSHHosts               []string // SSH_HOSTS env var, comma-separated
	SSHUser                string   // SSH_USER env var, default "vigil-agent"
	SSHKeyPath             string   // SSH_KEY_PATH env var, default "~/.ssh/id_ed25519"
	MaxOutputBytesDescribe int
}

// Load reads configuration from environment variables with sensible defaults.
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
	}
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}
