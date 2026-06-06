package nixos

import (
	"fmt"
	"path"
	"strings"
)

var allowList = map[string]map[string]bool{
	"nix-env":                 {},
	"nixos-rebuild":           {"test": true, "dry-activate": true},
	"switch-to-configuration": {"test": true, "boot": true},
	"systemctl":               {"is-active": true, "status": true, "start": true, "stop": true, "restart": true},
	"sysctl":                  {},
	"journalctl":              {},
	"etcdctl":                 {"snapshot": true},
	"kubectl":                 {"get": true},
}

var restartableUnits = map[string]bool{
	"systemd-sysctl": true,
}

func splitChainedCommand(cmd string) []string {
	segments := strings.Split(cmd, "&&")
	trimmed := make([]string, 0, len(segments))
	for _, seg := range segments {
		seg = strings.TrimSpace(seg)
		if seg != "" {
			trimmed = append(trimmed, seg)
		}
	}
	return trimmed
}

func commandTokens(segment string) []string {
	fields := strings.Fields(segment)
	if len(fields) > 0 && fields[0] == "sudo" {
		fields = fields[1:]
	}
	return fields
}

func firstSubCommand(args []string) (string, bool) {
	for _, arg := range args {
		if !strings.HasPrefix(arg, "-") {
			return arg, true
		}
	}
	return "", false
}

func validateCommand(cmd string) error {
	segments := splitChainedCommand(cmd)
	if len(segments) == 0 {
		return fmt.Errorf("empty command")
	}
	for _, segment := range segments {
		tokens := commandTokens(segment)
		if len(tokens) == 0 {
			return fmt.Errorf("empty command segment")
		}
		binary := path.Base(tokens[0])
		permitted, ok := allowList[binary]
		if !ok {
			return fmt.Errorf("command not in allow-list: %s", binary)
		}
		if len(permitted) == 0 {
			continue
		}
		sub, found := firstSubCommand(tokens[1:])
		if !found || !permitted[sub] {
			return fmt.Errorf("sub-command not in allow-list: %s %s", binary, sub)
		}
		if binary == "systemctl" && sub == "restart" {
			if err := validateRestartUnit(tokens); err != nil {
				return err
			}
		}
	}
	return nil
}

func validateRestartUnit(tokens []string) error {
	args := tokens[1:]
	seenRestart := false
	for _, arg := range args {
		if strings.HasPrefix(arg, "-") {
			continue
		}
		if !seenRestart {
			seenRestart = true
			continue
		}
		if !restartableUnits[arg] {
			return fmt.Errorf("systemctl restart unit not in allow-list: %s", arg)
		}
		return nil
	}
	return fmt.Errorf("systemctl restart requires an allow-listed unit")
}
