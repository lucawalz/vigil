package flux

import (
	"fmt"
	"strings"
)

func truncateOutput(s string, maxBytes int) string {
	if len(s) <= maxBytes {
		return s
	}
	clipped := s[:maxBytes]
	clippedLines := strings.Split(clipped, "\n")
	totalLines := len(strings.Split(s, "\n"))
	omitted := totalLines - len(clippedLines)
	return strings.Join(clippedLines, "\n") + fmt.Sprintf("\n[TRUNCATED: %d lines omitted]", omitted)
}
