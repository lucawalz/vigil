package ssh

import (
	"strings"
	"testing"
)

func TestTruncateOutput_NoTruncation(t *testing.T) {
	s := "short output"
	result := truncateOutput(s, 1024)
	if result != s {
		t.Errorf("expected unchanged output %q, got %q", s, result)
	}
}

func TestTruncateOutput_Truncates(t *testing.T) {
	s := strings.Repeat("line\n", 500)
	result := truncateOutput(s, 100)
	if !strings.Contains(result, "[TRUNCATED:") {
		t.Errorf("expected truncation marker, got: %s", result[:50])
	}
}

func TestTruncateOutput_CountsOmittedLines(t *testing.T) {
	var lines []string
	for i := 0; i < 10; i++ {
		lines = append(lines, strings.Repeat("x", 10))
	}
	s := strings.Join(lines, "\n") + "\n"
	result := truncateOutput(s, 25)
	if !strings.Contains(result, "[TRUNCATED:") {
		t.Errorf("expected truncation marker")
	}
	if strings.Contains(result, "[TRUNCATED: 0 lines omitted]") {
		t.Errorf("omitted count should not be zero")
	}
}

func TestTruncateOutput_ExactMaxBytes(t *testing.T) {
	s := strings.Repeat("x", 4096)
	result := truncateOutput(s, 4096)
	if result != s {
		t.Errorf("input at exact maxBytes should not be truncated")
	}
}

func TestTruncateOutput_OneByteOver(t *testing.T) {
	s := strings.Repeat("x", 4097)
	result := truncateOutput(s, 4096)
	if !strings.Contains(result, "[TRUNCATED:") {
		t.Errorf("input one byte over maxBytes should be truncated")
	}
}
