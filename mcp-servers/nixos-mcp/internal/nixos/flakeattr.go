package nixos

import (
	"context"
	"fmt"
	"regexp"
	"strings"
)

const (
	flakeAttrPath        = "/etc/vigil/flake-attr"
	readFlakeAttrCommand = "cat " + flakeAttrPath
	flakeCheckout        = "/opt/vigil/infra/nixos"
)

var flakeAttrRE = regexp.MustCompile(`^[a-z0-9-]+$`)

func rebuildCommand(action, rawAttr string) (string, error) {
	attr := strings.TrimSpace(rawAttr)
	if !flakeAttrRE.MatchString(attr) {
		return "", fmt.Errorf("%s holds an invalid flake attribute %q", flakeAttrPath, attr)
	}
	return fmt.Sprintf("sudo nixos-rebuild %s --flake %s#%s", action, flakeCheckout, attr), nil
}

func (c *realNixOSClient) flakeRebuildCommand(ctx context.Context, host, action string) (string, error) {
	raw, err := c.runCommand(ctx, host, readFlakeAttrCommand)
	if err != nil {
		return "", fmt.Errorf("read %s on %s: %w", flakeAttrPath, host, err)
	}
	return rebuildCommand(action, raw)
}
