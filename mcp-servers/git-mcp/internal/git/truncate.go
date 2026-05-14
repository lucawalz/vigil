package git

import (
	"fmt"
	"strings"
)

func truncateOutput(s string, maxBytes int) string {
	if len(s) <= maxBytes {
		return s
	}
	clipped := s[:maxBytes]
	shown := len(strings.Split(strings.TrimRight(clipped, "\n"), "\n"))
	total := len(strings.Split(s, "\n"))
	omitted := total - shown
	return strings.TrimRight(clipped, "\n") + fmt.Sprintf("\n[TRUNCATED: %d lines omitted]", omitted)
}
