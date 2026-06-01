package git

import (
	"os"
	"strings"
)

const ProtectedBranchesEnv = "VIGIL_PROTECTED_BRANCHES"

const ProtectedBranchesDefault = "main"

type ProtectedBranches map[string]struct{}

func LoadProtectedBranches() ProtectedBranches {
	raw := os.Getenv(ProtectedBranchesEnv)
	if raw == "" {
		raw = ProtectedBranchesDefault
	}
	protected := ProtectedBranches{}
	for _, branch := range strings.Split(raw, ",") {
		trimmed := strings.TrimSpace(branch)
		if trimmed == "" {
			continue
		}
		protected[trimmed] = struct{}{}
	}
	return protected
}

func (p ProtectedBranches) Contains(branch string) bool {
	_, ok := p[branch]
	return ok
}
