package git

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

var errNotFound = errors.New("resource not found in kustomize tree")

const maxKustomizeDepth = 8

type resourceCandidate struct {
	kind      string
	namespace string
	name      string
	path      string
}

func resolveManifestPath(cloneDir, specPath, kind, namespace, name string) (string, string, error) {
	specPath = strings.TrimPrefix(strings.TrimPrefix(specPath, "./"), "/")
	absRoot := filepath.Join(cloneDir, specPath)

	var candidates []resourceCandidate
	absMatch, err := walkKustomize(cloneDir, absRoot, kind, namespace, name, &candidates, 0)
	if err != nil {
		if errors.Is(err, errNotFound) {
			return "", buildHint(candidates), errNotFound
		}
		return "", "", err
	}

	rel, relErr := filepath.Rel(cloneDir, absMatch)
	if relErr != nil {
		return "", "", fmt.Errorf("resolve relative path: %w", relErr)
	}
	return rel, "", nil
}

func buildHint(candidates []resourceCandidate) string {
	if len(candidates) == 0 {
		return "no resources discovered in kustomize tree"
	}
	var b strings.Builder
	b.WriteString("discovered resources: ")
	for i, c := range candidates {
		if i > 0 {
			b.WriteString(", ")
		}
		ns := c.namespace
		if ns == "" {
			ns = "default"
		}
		fmt.Fprintf(&b, "%s/%s/%s at %s", c.kind, ns, c.name, c.path)
	}
	return b.String()
}

func walkKustomize(cloneDir, dir, kind, namespace, name string, candidates *[]resourceCandidate, depth int) (string, error) {
	if depth > maxKustomizeDepth {
		return "", fmt.Errorf("kustomize walk: max depth %d exceeded at %s", maxKustomizeDepth, dir)
	}

	kPath := findKustomizationFile(dir)
	if kPath == "" {
		return scanYAMLDir(cloneDir, dir, kind, namespace, name, candidates, depth)
	}

	resources, err := readKustomizationResources(kPath)
	if err != nil {
		return "", fmt.Errorf("kustomize walk: %w", err)
	}

	for _, res := range resources {
		absRes := filepath.Join(dir, res)
		stat, statErr := os.Stat(absRes)
		if statErr != nil {
			continue
		}
		if stat.IsDir() {
			if match, walkErr := walkKustomize(cloneDir, absRes, kind, namespace, name, candidates, depth+1); walkErr == nil {
				return match, nil
			} else if !errors.Is(walkErr, errNotFound) {
				return "", walkErr
			}
		} else if isYAMLFile(res) {
			if match, checkErr := checkYAMLFile(cloneDir, absRes, kind, namespace, name, candidates); checkErr == nil {
				return match, nil
			}
		}
	}
	return "", errNotFound
}

func findKustomizationFile(dir string) string {
	for _, n := range []string{"kustomization.yaml", "kustomization.yml", "Kustomization"} {
		p := filepath.Join(dir, n)
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

func readKustomizationResources(kPath string) ([]string, error) {
	data, err := os.ReadFile(kPath)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", kPath, err)
	}
	var k struct {
		Resources []string `yaml:"resources"`
	}
	if err := yaml.Unmarshal(data, &k); err != nil {
		return nil, fmt.Errorf("parse %s: %w", kPath, err)
	}
	return k.Resources, nil
}

func isYAMLFile(path string) bool {
	ext := strings.ToLower(filepath.Ext(path))
	return ext == ".yaml" || ext == ".yml"
}

func checkYAMLFile(cloneDir, absPath, wantKind, wantNS, wantName string, candidates *[]resourceCandidate) (string, error) {
	data, err := os.ReadFile(absPath)
	if err != nil {
		return "", err
	}
	rel, _ := filepath.Rel(cloneDir, absPath)

	type docHeader struct {
		Kind     string `yaml:"kind"`
		Metadata struct {
			Name      string `yaml:"name"`
			Namespace string `yaml:"namespace"`
		} `yaml:"metadata"`
	}

	decoder := yaml.NewDecoder(bytes.NewReader(data))
	for {
		var doc docHeader
		if decErr := decoder.Decode(&doc); decErr != nil {
			if errors.Is(decErr, io.EOF) {
				break
			}
			break
		}
		if doc.Kind == "" && doc.Metadata.Name == "" {
			continue
		}
		ns := doc.Metadata.Namespace
		if ns == "" {
			ns = "default"
		}
		*candidates = append(*candidates, resourceCandidate{
			kind:      doc.Kind,
			namespace: ns,
			name:      doc.Metadata.Name,
			path:      rel,
		})
		wantNSNorm := wantNS
		if wantNSNorm == "" {
			wantNSNorm = "default"
		}
		if strings.EqualFold(doc.Kind, wantKind) && doc.Metadata.Name == wantName && ns == wantNSNorm {
			return absPath, nil
		}
	}
	return "", errNotFound
}

func scanYAMLDir(cloneDir, dir, kind, namespace, name string, candidates *[]resourceCandidate, depth int) (string, error) {
	if depth > maxKustomizeDepth {
		return "", fmt.Errorf("kustomize walk: max depth %d exceeded at %s", maxKustomizeDepth, dir)
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return "", fmt.Errorf("scan dir %s: %w", dir, err)
	}
	for _, e := range entries {
		absPath := filepath.Join(dir, e.Name())
		if e.IsDir() {
			if match, walkErr := walkKustomize(cloneDir, absPath, kind, namespace, name, candidates, depth+1); walkErr == nil {
				return match, nil
			} else if !errors.Is(walkErr, errNotFound) {
				return "", walkErr
			}
			continue
		}
		if !isYAMLFile(e.Name()) {
			continue
		}
		if match, checkErr := checkYAMLFile(cloneDir, absPath, kind, namespace, name, candidates); checkErr == nil {
			return match, nil
		}
	}
	return "", errNotFound
}
