package flux

import (
	"strings"
	"testing"
)

func TestTruncateOutput_NoTruncation(t *testing.T) {
	s := "short output"
	if truncateOutput(s, 1024) != s {
		t.Error("expected unchanged output")
	}
}

func TestTruncateOutput_Truncates(t *testing.T) {
	s := strings.Repeat("line\n", 500)
	if !strings.Contains(truncateOutput(s, 100), "[TRUNCATED:") {
		t.Error("expected truncation marker")
	}
}
