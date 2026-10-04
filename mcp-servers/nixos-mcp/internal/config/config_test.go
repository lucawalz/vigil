package config

import (
	"reflect"
	"testing"
)

func TestParseSSHHosts(t *testing.T) {
	tests := []struct {
		name    string
		raw     string
		want    []SSHHost
		wantErr bool
	}{
		{name: "bare name dials port 22", raw: "vigil-worker-1", want: []SSHHost{{Name: "vigil-worker-1", Addr: "vigil-worker-1:22"}}},
		{name: "name and port dial the loopback forward", raw: "vigil-worker-1:2211,vigil-worker-2:2212", want: []SSHHost{{Name: "vigil-worker-1", Addr: "127.0.0.1:2211"}, {Name: "vigil-worker-2", Addr: "127.0.0.1:2212"}}},
		{name: "mixed entries", raw: "vigil-worker-1, vigil-worker-2:2212", want: []SSHHost{{Name: "vigil-worker-1", Addr: "vigil-worker-1:22"}, {Name: "vigil-worker-2", Addr: "127.0.0.1:2212"}}},
		{name: "empty value configures no hosts", raw: "", want: nil},
		{name: "non-numeric port", raw: "vigil-worker-1:ssh", wantErr: true},
		{name: "port above range", raw: "vigil-worker-1:65536", wantErr: true},
		{name: "port zero", raw: "vigil-worker-1:0", wantErr: true},
		{name: "duplicate name", raw: "vigil-worker-1,vigil-worker-1:2211", wantErr: true},
		{name: "empty entry", raw: "vigil-worker-1,,vigil-worker-2", wantErr: true},
		{name: "empty name", raw: ":2211", wantErr: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParseSSHHosts(tt.raw)
			if tt.wantErr {
				if err == nil {
					t.Fatalf("expected an error for %q, got %+v", tt.raw, got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("got %+v; want %+v", got, tt.want)
			}
		})
	}
}

func TestLoadRejectsInvalidSSHHosts(t *testing.T) {
	t.Setenv("SSH_HOSTS", "vigil-worker-1:ssh")
	if _, err := Load(); err == nil {
		t.Fatal("expected Load to reject an invalid SSH_HOSTS entry")
	}
}
