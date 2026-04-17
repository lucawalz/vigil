package config

import (
	"fmt"
	"os"
	"strconv"

	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

const (
	MaxOutputBytesDescribe   = 4096
	MaxOutputBytesLogs       = 2048
	MaxOutputBytesPrometheus = 10240
)

type Config struct {
	MaxOutputBytesDescribe   int
	MaxOutputBytesLogs       int
	MaxOutputBytesPrometheus int
}

func Load() *Config {
	return &Config{
		MaxOutputBytesDescribe:   envInt("MAX_OUTPUT_BYTES_DESCRIBE", MaxOutputBytesDescribe),
		MaxOutputBytesLogs:       envInt("MAX_OUTPUT_BYTES_LOGS", MaxOutputBytesLogs),
		MaxOutputBytesPrometheus: envInt("MAX_OUTPUT_BYTES_PROMETHEUS", MaxOutputBytesPrometheus),
	}
}

func BuildRestConfig() (*rest.Config, error) {
	loadingRules := clientcmd.NewDefaultClientConfigLoadingRules()
	cfg, err := clientcmd.NewNonInteractiveDeferredLoadingClientConfig(
		loadingRules,
		&clientcmd.ConfigOverrides{},
	).ClientConfig()
	if err != nil {
		return nil, fmt.Errorf("kubeconfig: %w", err)
	}
	return cfg, nil
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return fallback
}
