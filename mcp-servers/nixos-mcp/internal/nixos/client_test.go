package nixos

import (
	"context"
	"strings"
	"testing"
)

func labClient() *realNixOSClient {
	return &realNixOSClient{hostAddrs: map[string]string{
		"vigil-worker-1": "127.0.0.1:2211",
		"vigil-worker-2": "vigil-worker-2:22",
	}}
}

func TestDialAddressForConfiguredHosts(t *testing.T) {
	tests := []struct {
		host    string
		want    string
		wantErr bool
	}{
		{host: "vigil-worker-1", want: "127.0.0.1:2211"},
		{host: "vigil-worker-2", want: "vigil-worker-2:22"},
		{host: "vigil-control-plane-1", wantErr: true},
	}
	for _, tt := range tests {
		t.Run(tt.host, func(t *testing.T) {
			got, err := labClient().dialAddress(tt.host)
			if tt.wantErr {
				if err == nil || !strings.Contains(err.Error(), "allow-list") {
					t.Fatalf("expected an allow-list error, got %q, %v", got, err)
				}
				return
			}
			if err != nil || got != tt.want {
				t.Fatalf("dialAddress(%q) = %q, %v; want %q", tt.host, got, err, tt.want)
			}
		})
	}
}

func TestDialAddressWithoutConfiguredHosts(t *testing.T) {
	_, err := (&realNixOSClient{}).dialAddress("vigil-worker-1")
	if err == nil || !strings.Contains(err.Error(), "SSH_HOSTS is not configured") {
		t.Fatalf("expected the unconfigured error, got %v", err)
	}
}

func TestGetNixPathAcceptsOnlyConfiguredHosts(t *testing.T) {
	got, err := labClient().GetNixPath(context.Background(), "vigil-worker-1")
	if err != nil || got != "infra/nixos/hosts/vigil-worker-1/default.nix" {
		t.Fatalf("GetNixPath = %q, %v", got, err)
	}
	if _, err := labClient().GetNixPath(context.Background(), "vigil-agent"); err == nil {
		t.Fatal("expected an unknown hostname error for a host outside SSH_HOSTS")
	}
}
