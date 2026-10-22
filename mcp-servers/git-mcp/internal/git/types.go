package git

type TextResult struct {
	Text string `json:"text" jsonschema:"Output text"`
}

type CommitResult struct {
	SHA string `json:"sha" jsonschema:"Commit SHA"`
}

type RevertResult struct {
	SHA            string `json:"sha" jsonschema:"Revert commit SHA on the revert branch"`
	PRNumber       int    `json:"pr_number" jsonschema:"Pull request number of the revert"`
	MergeCommitSHA string `json:"merge_commit_sha" jsonschema:"SHA of the commit the revert pull request merged into the base branch"`
}

type PRNumberResult struct {
	PRNumber int `json:"pr_number" jsonschema:"Pull request number"`
}

type PRStatusResult struct {
	State          string `json:"state" jsonschema:"PR state: open or closed"`
	Merged         bool   `json:"merged" jsonschema:"Whether the PR was merged"`
	MergeCommitSHA string `json:"merge_commit_sha" jsonschema:"Merge commit SHA if merged, empty otherwise"`
}

type GatePassedResult struct {
	MergeCommitSHA string `json:"merge_commit_sha" jsonschema:"SHA of the merge commit"`
}

type ManifestPathResult struct {
	Path string `json:"path" jsonschema:"Repo-relative path to the manifest file"`
}

type ReadFileResult struct {
	Branch  string `json:"branch" jsonschema:"Branch the file was read from"`
	Path    string `json:"path" jsonschema:"Repo-relative file path"`
	Content string `json:"content" jsonschema:"File content (may be truncated)"`
}
