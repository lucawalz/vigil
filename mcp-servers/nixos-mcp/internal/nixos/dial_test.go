package nixos

import (
	"context"
	"errors"
	"net"
	"syscall"
	"testing"
	"time"
)

type timeoutError struct{}

func (timeoutError) Error() string   { return "i/o timeout" }
func (timeoutError) Timeout() bool   { return true }
func (timeoutError) Temporary() bool { return true }

func newTestClient(dial dialFunc) *realNixOSClient {
	return &realNixOSClient{
		allowedHosts: []string{"hetzner-master"},
		dialTimeout:  time.Second,
		dialRetries:  3,
		dialBackoff:  time.Millisecond,
		dialFunc:     dial,
	}
}

func TestDialWithRetrySucceedsAfterTransientTimeouts(t *testing.T) {
	var attempts int
	dial := func(_ context.Context, _, _ string) (net.Conn, error) {
		attempts++
		if attempts < 3 {
			return nil, timeoutError{}
		}
		return nil, nil
	}

	c := newTestClient(dial)
	if _, err := c.dialWithRetry(context.Background(), "hetzner-master:22"); err != nil {
		t.Fatalf("expected success after transient timeouts, got: %v", err)
	}
	if attempts != 3 {
		t.Errorf("expected 3 attempts, got %d", attempts)
	}
}

func TestDialWithRetryRetriesConnectionRefused(t *testing.T) {
	var attempts int
	dial := func(_ context.Context, _, _ string) (net.Conn, error) {
		attempts++
		if attempts < 2 {
			return nil, syscall.ECONNREFUSED
		}
		return nil, nil
	}

	c := newTestClient(dial)
	if _, err := c.dialWithRetry(context.Background(), "hetzner-master:22"); err != nil {
		t.Fatalf("expected success after connection refused, got: %v", err)
	}
	if attempts != 2 {
		t.Errorf("expected 2 attempts, got %d", attempts)
	}
}

func TestDialWithRetryDoesNotRetryNonTransientError(t *testing.T) {
	var attempts int
	nonTransient := errors.New("permission denied")
	dial := func(_ context.Context, _, _ string) (net.Conn, error) {
		attempts++
		return nil, nonTransient
	}

	c := newTestClient(dial)
	_, err := c.dialWithRetry(context.Background(), "hetzner-master:22")
	if !errors.Is(err, nonTransient) {
		t.Fatalf("expected non-transient error returned immediately, got: %v", err)
	}
	if attempts != 1 {
		t.Errorf("expected exactly 1 attempt for non-transient error, got %d", attempts)
	}
}

func TestDialWithRetryExhaustsBudget(t *testing.T) {
	var attempts int
	dial := func(_ context.Context, _, _ string) (net.Conn, error) {
		attempts++
		return nil, timeoutError{}
	}

	c := newTestClient(dial)
	_, err := c.dialWithRetry(context.Background(), "hetzner-master:22")
	if err == nil {
		t.Fatal("expected error after exhausting retry budget")
	}
	if attempts != 3 {
		t.Errorf("expected 3 attempts before exhaustion, got %d", attempts)
	}
}

func TestDialWithRetryHonorsContextCancellation(t *testing.T) {
	var attempts int
	dial := func(_ context.Context, _, _ string) (net.Conn, error) {
		attempts++
		return nil, timeoutError{}
	}

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	c := newTestClient(dial)
	_, err := c.dialWithRetry(ctx, "hetzner-master:22")
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got: %v", err)
	}
	if attempts > 1 {
		t.Errorf("expected at most 1 attempt before honoring cancellation, got %d", attempts)
	}
}
