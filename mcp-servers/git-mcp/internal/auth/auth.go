package auth

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"net/http"
	"os"
	"sync"
	"time"

	gogithub "github.com/google/go-github/v86/github"
	"golang.org/x/oauth2"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
)

const (
	jwtBackdate        = 60 * time.Second
	jwtLifetime        = 9 * time.Minute
	tokenRefreshMargin = time.Minute
	githubCallTimeout  = 30 * time.Second
	jwtHeader          = `{"alg":"RS256","typ":"JWT"}`
	defaultAuthorName  = "vigil-remediation"
	defaultAuthorEmail = "remediation@vigil.local"
)

type TokenFunc func(ctx context.Context) (string, error)

func (f TokenFunc) Token() (*oauth2.Token, error) {
	token, err := f(context.Background())
	if err != nil {
		return nil, err
	}
	return &oauth2.Token{AccessToken: token}, nil
}

func (f TokenFunc) HTTPClient() *http.Client {
	return &http.Client{Transport: &oauth2.Transport{Source: f}, Timeout: githubCallTimeout}
}

type Identity struct {
	Token       TokenFunc
	AuthorName  string
	AuthorEmail string
}

func Static(token string) TokenFunc {
	return func(context.Context) (string, error) { return token, nil }
}

func NewTokenFunc(ctx context.Context, cfg *config.Config) (TokenFunc, error) {
	if !cfg.UsesApp() {
		return Static(cfg.GitHubToken), nil
	}
	_, token, err := appTokenFunc(ctx, cfg)
	return token, err
}

func NewIdentity(ctx context.Context, cfg *config.Config) (Identity, error) {
	if !cfg.UsesApp() {
		return Identity{Token: Static(cfg.GitHubToken), AuthorName: defaultAuthorName, AuthorEmail: defaultAuthorEmail}, nil
	}
	gh, token, err := appTokenFunc(ctx, cfg)
	if err != nil {
		return Identity{}, err
	}
	return botIdentity(ctx, gh, token)
}

func appTokenFunc(ctx context.Context, cfg *config.Config) (*gogithub.Client, TokenFunc, error) {
	owner, repo, err := cfg.Repository()
	if err != nil {
		return nil, nil, err
	}
	pemBytes, err := os.ReadFile(cfg.AppPrivateKeyFile)
	if err != nil {
		return nil, nil, fmt.Errorf("read GITHUB_APP_PRIVATE_KEY_FILE: %w", err)
	}
	key, err := parsePrivateKey(pemBytes)
	if err != nil {
		return nil, nil, fmt.Errorf("parse GITHUB_APP_PRIVATE_KEY_FILE: %w", err)
	}
	gh := newAppClient(cfg.AppClientID, key)
	token, err := installationTokenFunc(ctx, gh, owner, repo)
	return gh, token, err
}

func newAppClient(clientID string, key *rsa.PrivateKey) *gogithub.Client {
	jwt := TokenFunc(func(context.Context) (string, error) { return signJWT(clientID, key, time.Now()) })
	return gogithub.NewClient(jwt.HTTPClient())
}

func installationTokenFunc(ctx context.Context, gh *gogithub.Client, owner, repo string) (TokenFunc, error) {
	inst, _, err := gh.Apps.FindRepositoryInstallation(ctx, owner, repo)
	if err != nil {
		return nil, fmt.Errorf("find app installation for %s/%s: %w", owner, repo, err)
	}
	tok := &installationToken{mint: func(ctx context.Context) (string, time.Time, error) {
		it, _, err := gh.Apps.CreateInstallationToken(ctx, inst.GetID(), nil)
		if err != nil {
			return "", time.Time{}, fmt.Errorf("create installation token: %w", err)
		}
		return it.GetToken(), it.GetExpiresAt().Time, nil
	}}
	return tok.get, nil
}

type installationToken struct {
	mu        sync.Mutex
	mint      func(ctx context.Context) (string, time.Time, error)
	token     string
	expiresAt time.Time
}

func (t *installationToken) get(ctx context.Context) (string, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.token != "" && time.Until(t.expiresAt) > tokenRefreshMargin {
		return t.token, nil
	}
	token, expiresAt, err := t.mint(ctx)
	if err != nil {
		return "", err
	}
	t.token, t.expiresAt = token, expiresAt
	return token, nil
}

func botIdentity(ctx context.Context, appGH *gogithub.Client, token TokenFunc) (Identity, error) {
	app, _, err := appGH.Apps.Get(ctx, "")
	if err != nil {
		return Identity{}, fmt.Errorf("get app: %w", err)
	}
	installGH := gogithub.NewClient(token.HTTPClient())
	installGH.BaseURL = appGH.BaseURL
	user, _, err := installGH.Users.Get(ctx, app.GetSlug()+"[bot]")
	if err != nil {
		return Identity{}, fmt.Errorf("get bot user for app %s: %w", app.GetSlug(), err)
	}
	name, email := botAuthor(app.GetSlug(), user.GetID())
	return Identity{Token: token, AuthorName: name, AuthorEmail: email}, nil
}

func botAuthor(slug string, userID int64) (name, email string) {
	name = slug + "[bot]"
	return name, fmt.Sprintf("%d+%s@users.noreply.github.com", userID, name)
}

func signJWT(clientID string, key *rsa.PrivateKey, now time.Time) (string, error) {
	claims, err := json.Marshal(struct {
		IssuedAt  int64  `json:"iat"`
		ExpiresAt int64  `json:"exp"`
		Issuer    string `json:"iss"`
	}{now.Add(-jwtBackdate).Unix(), now.Add(jwtLifetime).Unix(), clientID})
	if err != nil {
		return "", err
	}
	enc := base64.RawURLEncoding
	signingInput := enc.EncodeToString([]byte(jwtHeader)) + "." + enc.EncodeToString(claims)
	digest := sha256.Sum256([]byte(signingInput))
	sig, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, digest[:])
	if err != nil {
		return "", fmt.Errorf("sign app jwt: %w", err)
	}
	return signingInput + "." + enc.EncodeToString(sig), nil
}

func parsePrivateKey(pemBytes []byte) (*rsa.PrivateKey, error) {
	block, _ := pem.Decode(pemBytes)
	if block == nil {
		return nil, errors.New("no PEM block found")
	}
	if key, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return key, nil
	}
	parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("parse private key: %w", err)
	}
	key, ok := parsed.(*rsa.PrivateKey)
	if !ok {
		return nil, errors.New("private key is not RSA")
	}
	return key, nil
}
