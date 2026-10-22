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
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

const (
	testClientID       = "Iv23test"
	testInstallationID = 42
	testKeyBits        = 2048
)

func testKey(t *testing.T) *rsa.PrivateKey {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, testKeyBits)
	if err != nil {
		t.Fatal(err)
	}
	return key
}

func verifyJWT(t *testing.T, token string, pub *rsa.PublicKey) map[string]any {
	t.Helper()
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		t.Fatalf("jwt has %d parts, want 3", len(parts))
	}
	sig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	if err := rsa.VerifyPKCS1v15(pub, crypto.SHA256, sum[:], sig); err != nil {
		t.Fatalf("jwt signature does not verify: %v", err)
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		t.Fatal(err)
	}
	var claims map[string]any
	if err := json.Unmarshal(payload, &claims); err != nil {
		t.Fatal(err)
	}
	return claims
}

func TestSignJWT_verifiesAndCarriesClientID(t *testing.T) {
	key := testKey(t)
	now := time.Unix(1_700_000_000, 0)

	token, err := signJWT(testClientID, key, now)
	if err != nil {
		t.Fatalf("signJWT: %v", err)
	}
	claims := verifyJWT(t, token, &key.PublicKey)
	if claims["iss"] != testClientID {
		t.Errorf("iss = %v, want %s", claims["iss"], testClientID)
	}
	if claims["iat"] != float64(now.Add(-jwtBackdate).Unix()) || claims["exp"] != float64(now.Add(jwtLifetime).Unix()) {
		t.Errorf("unexpected iat/exp: %v", claims)
	}
}

func TestParsePrivateKey_pkcs1AndPkcs8(t *testing.T) {
	key := testKey(t)
	pkcs8, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	blocks := map[string]*pem.Block{
		"pkcs1": {Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)},
		"pkcs8": {Type: "PRIVATE KEY", Bytes: pkcs8},
	}
	for name, block := range blocks {
		got, err := parsePrivateKey(pem.EncodeToMemory(block))
		if err != nil || !got.Equal(key) {
			t.Errorf("%s: parsePrivateKey = %v", name, err)
		}
	}
	if _, err := parsePrivateKey([]byte("not pem")); err == nil {
		t.Error("expected error for non-PEM input")
	}
}

func TestInstallationToken_mintsAgainWhenExpired(t *testing.T) {
	key := testKey(t)
	var mints atomic.Int32
	mux := http.NewServeMux()
	mux.HandleFunc("GET /repos/o/r/installation", func(w http.ResponseWriter, r *http.Request) {
		verifyJWT(t, strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer "), &key.PublicKey)
		_, _ = fmt.Fprintf(w, `{"id":%d}`, testInstallationID)
	})
	mux.HandleFunc(fmt.Sprintf("POST /app/installations/%d/access_tokens", testInstallationID), func(w http.ResponseWriter, r *http.Request) {
		verifyJWT(t, strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer "), &key.PublicKey)
		n := mints.Add(1)
		expired := time.Now().Add(-time.Hour).UTC().Format(time.RFC3339)
		_, _ = fmt.Fprintf(w, `{"token":"tok-%d","expires_at":%q}`, n, expired)
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	gh := newAppClient(testClientID, key)
	gh.BaseURL, _ = url.Parse(srv.URL + "/")

	token, err := installationTokenFunc(context.Background(), gh, "o", "r")
	if err != nil {
		t.Fatalf("installationTokenFunc: %v", err)
	}
	first, err := token(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	second, err := token(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if first == second || mints.Load() != 2 {
		t.Errorf("first=%q second=%q mints=%d, want two distinct tokens from two mints", first, second, mints.Load())
	}
}

func TestInstallationToken_reusesValidToken(t *testing.T) {
	var mints atomic.Int32
	tok := &installationToken{mint: func(context.Context) (string, time.Time, error) {
		mints.Add(1)
		return "tok", time.Now().Add(time.Hour), nil
	}}
	for range 2 {
		if _, err := tok.get(context.Background()); err != nil {
			t.Fatal(err)
		}
	}
	if mints.Load() != 1 {
		t.Errorf("mints = %d, want 1", mints.Load())
	}
}

func TestBotAuthor(t *testing.T) {
	name, email := botAuthor("vigil-agent", 123456)
	if name != "vigil-agent[bot]" {
		t.Errorf("name = %q", name)
	}
	if email != "123456+vigil-agent[bot]@users.noreply.github.com" {
		t.Errorf("email = %q", email)
	}
}
