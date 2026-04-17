package ssh

import (
	"fmt"
	"regexp"
)

var allowList = map[string]map[string]bool{
	"journalctl": {},                                                         // any args
	"systemctl":  {"status": true, "is-active": true, "is-failed": true},    // read-only sub-commands only
	"free":       {},
	"df":         {},
	"uptime":     {},
	"ip":         {"addr": true, "route": true, "link": true},
	"ss":         {},
}

var shellMetaRE = regexp.MustCompile(`[;&|$` + "`" + `(){}<>]`)

func validateCommand(binary string, args []string) error {
	permitted, ok := allowList[binary]
	if !ok {
		return fmt.Errorf("command not in allow-list: %s", binary)
	}
	for _, arg := range args {
		if shellMetaRE.MatchString(arg) {
			return fmt.Errorf("argument contains shell metacharacter: %q", arg)
		}
	}
	if len(permitted) > 0 && len(args) > 0 {
		if !permitted[args[0]] {
			return fmt.Errorf("sub-command not in allow-list: %s %s", binary, args[0])
		}
	}
	return nil
}
