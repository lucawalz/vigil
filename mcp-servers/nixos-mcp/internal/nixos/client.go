package nixos

import (
	"context"
	"fmt"
)

type NixOSClient interface {
	GetGenerations(ctx context.Context, host string) (string, error)
	SwitchGeneration(ctx context.Context, host string, generation int) (string, error)
	RebuildTest(ctx context.Context, host string) (string, error)
	GetJournal(ctx context.Context, host, unit string, lines int) (string, error)
	GetSystemdStatus(ctx context.Context, host, unit string) (string, error)
	EtcdSnapshotSave(ctx context.Context, host, destPath string) (string, error)
}

type stubNixOSClient struct{}

func NewRealNixOSClient(user, keyPath string) (NixOSClient, error) {
	return &stubNixOSClient{}, nil
}

func (c *stubNixOSClient) GetGenerations(_ context.Context, _ string) (string, error) {
	return "", fmt.Errorf("not implemented")
}

func (c *stubNixOSClient) SwitchGeneration(_ context.Context, _ string, _ int) (string, error) {
	return "", fmt.Errorf("not implemented")
}

func (c *stubNixOSClient) RebuildTest(_ context.Context, _ string) (string, error) {
	return "", fmt.Errorf("not implemented")
}

func (c *stubNixOSClient) GetJournal(_ context.Context, _, _ string, _ int) (string, error) {
	return "", fmt.Errorf("not implemented")
}

func (c *stubNixOSClient) GetSystemdStatus(_ context.Context, _, _ string) (string, error) {
	return "", fmt.Errorf("not implemented")
}

func (c *stubNixOSClient) EtcdSnapshotSave(_ context.Context, _, _ string) (string, error) {
	return "", fmt.Errorf("not implemented")
}
