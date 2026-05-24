package git

type TextResult struct {
	Text string `json:"text" jsonschema:"Output text"`
}

type CommitResult struct {
	SHA string `json:"sha" jsonschema:"Commit SHA"`
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
