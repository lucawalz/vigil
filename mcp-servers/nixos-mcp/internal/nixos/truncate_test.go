package nixos

import (
	"strings"
	"testing"
)

func TestTruncateOutput_ShortString(t *testing.T) {
	s := "short"
	if got := truncateOutput(s, 4096); got != s {
		t.Errorf("expected unchanged, got %q", got)
	}
}

func TestTruncateOutput_ExactLimit(t *testing.T) {
	s := strings.Repeat("a", 4096)
	if got := truncateOutput(s, 4096); got != s {
		t.Errorf("expected unchanged at exact limit")
	}
}

func TestTruncateOutput_Oversized(t *testing.T) {
	s := strings.Repeat("line\n", 2000) // well over 4096
	got := truncateOutput(s, 4096)
	if !strings.Contains(got, "[TRUNCATED:") {
		t.Errorf("expected truncation marker, got: %.100s", got)
	}
	if len(got) > 4096+100 {
		t.Errorf("truncated output too long: %d", len(got))
	}
}

func TestTruncateOutput_EmptyString(t *testing.T) {
	if got := truncateOutput("", 4096); got != "" {
		t.Errorf("expected empty, got %q", got)
	}
}

func TestTruncateOutput_TruncationMarkerFormat(t *testing.T) {
	s := strings.Repeat("x\n", 500)
	got := truncateOutput(s, 100)
	if !strings.Contains(got, "lines omitted]") {
		t.Errorf("expected 'lines omitted]' in marker, got: %s", got)
	}
}
