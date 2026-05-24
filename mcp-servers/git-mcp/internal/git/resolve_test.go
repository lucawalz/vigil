package git

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func buildResolverFixture(t *testing.T) string {
	t.Helper()
	root := t.TempDir()

	files := map[string]string{
		"clusters/hetzner/apps/kustomization.yaml": `apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - vigil-app.yaml
`,
		"clusters/hetzner/apps/vigil-app.yaml": `apiVersion: apps/v1
kind: Deployment
metadata:
  name: vigil-app
  namespace: default
spec:
  replicas: 1
`,
		"clusters/hetzner/infrastructure/kustomization.yaml": `apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - unrelated.yaml
`,
		"clusters/hetzner/infrastructure/unrelated.yaml": `apiVersion: v1
kind: Service
metadata:
  name: unrelated
  namespace: default
`,
		"clusters/hetzner/config/apps.yaml": `apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: cluster-apps
  namespace: flux-system
spec:
  path: ./clusters/hetzner/apps
`,
	}

	for rel, content := range files {
		abs := filepath.Join(root, rel)
		if err := os.MkdirAll(filepath.Dir(abs), 0o755); err != nil {
			t.Fatalf("mkdir %s: %v", filepath.Dir(abs), err)
		}
		if err := os.WriteFile(abs, []byte(content), 0o644); err != nil {
			t.Fatalf("write %s: %v", abs, err)
		}
	}
	return root
}

func TestResolveManifestPath(t *testing.T) {
	root := buildResolverFixture(t)

	cases := []struct {
		name       string
		specPath   string
		kind       string
		ns         string
		resName    string
		wantSuffix string
		wantErr    bool
		wantHint   bool
	}{
		{
			name:       "regression: parent spec path without kustomization.yaml recurses into apps subdir",
			specPath:   "clusters/hetzner",
			kind:       "Deployment",
			ns:         "default",
			resName:    "vigil-app",
			wantSuffix: "clusters/hetzner/apps/vigil-app.yaml",
		},
		{
			name:       "direct: spec path pointing directly at apps dir",
			specPath:   "clusters/hetzner/apps",
			kind:       "Deployment",
			ns:         "default",
			resName:    "vigil-app",
			wantSuffix: "clusters/hetzner/apps/vigil-app.yaml",
		},
		{
			name:     "not found: hint lists discovered candidates",
			specPath: "clusters/hetzner",
			kind:     "Deployment",
			ns:       "default",
			resName:  "does-not-exist",
			wantErr:  true,
			wantHint: true,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, hint, err := resolveManifestPath(root, tc.specPath, tc.kind, tc.ns, tc.resName)
			if tc.wantErr {
				if !errors.Is(err, errNotFound) {
					t.Fatalf("expected errNotFound, got %v", err)
				}
				if tc.wantHint && !strings.HasPrefix(hint, "discovered resources:") {
					t.Fatalf("expected non-empty hint, got %q", hint)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v (hint: %s)", err, hint)
			}
			if !strings.HasSuffix(filepath.ToSlash(got), tc.wantSuffix) {
				t.Fatalf("got path %q, want suffix %q", got, tc.wantSuffix)
			}
		})
	}
}
