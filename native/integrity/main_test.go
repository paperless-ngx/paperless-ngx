package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"testing"
	"time"
)

func testManifest(root string) manifest {
	return manifest{Version: 1, MediaRoot: root, Algorithm: "sha256", Files: []expectedFile{}, IgnoredFilenames: []string{}, ExcludedPaths: []string{}}
}

func writeFile(t *testing.T, root, name, content string) string {
	t.Helper()
	path := filepath.Join(root, name)
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return path
}

func digest(value string) string {
	hash := sha256.Sum256([]byte(value))
	return hex.EncodeToString(hash[:])
}

func TestGoldenFindings(t *testing.T) {
	root := t.TempDir()
	m := testManifest(root)
	for _, kind := range []string{"original", "archive", "thumbnail"} {
		m.Files = append(m.Files, expectedFile{DocumentID: 1, Kind: kind, Path: "missing-" + kind})
	}
	for _, kind := range []string{"original", "archive"} {
		path := writeFile(t, root, kind, "corrupt")
		m.Files = append(m.Files, expectedFile{DocumentID: 2, Kind: kind, Path: path, Checksum: digest("expected")})
	}
	writeFile(t, root, "orphan", "orphan")
	for _, name := range []string{"nested/.DS_Store", "media.lock", "logo.svg"} {
		writeFile(t, root, name, "excluded")
	}
	m.IgnoredFilenames = []string{".DS_Store"}
	m.ExcludedPaths = []string{filepath.Join(root, "media.lock"), "logo.svg", "absent-exclusion"}
	r := scan(context.Background(), m)
	counts := map[string]int{}
	for _, f := range r.Findings {
		counts[f.Code]++
		if f.Code == "checksum_mismatch" && f.ActualChecksum != digest("corrupt") {
			t.Fatalf("wrong SHA-256: %+v", f)
		}
	}
	if !r.Complete || r.CheckedFiles != 5 || counts["missing"] != 3 || counts["checksum_mismatch"] != 2 || counts["orphan"] != 1 || len(r.Findings) != 6 {
		t.Fatalf("unexpected golden findings: %+v", r)
	}
}

func TestUnicodeLongPathsAndReadOnly(t *testing.T) {
	root := t.TempDir()
	name := "目录 with spaces/" + strings.Repeat("long directory/", 30) + strings.Repeat("x", 180) + " 雪.pdf"
	path := writeFile(t, root, name, "synthetic document")
	m := testManifest(root)
	m.Files = []expectedFile{{DocumentID: 1, Kind: "original", Path: path, Checksum: digest("synthetic document")}}
	before, _ := os.Stat(path)
	r := scan(context.Background(), m)
	after, _ := os.Stat(path)
	content, _ := os.ReadFile(path)
	if !r.Complete || len(r.Findings) != 0 || !unchanged(before, after) || string(content) != "synthetic document" {
		t.Fatalf("unexpected Unicode/read-only result: %+v", r)
	}
}

func TestSafeAndUnsafeSymlinks(t *testing.T) {
	root := t.TempDir()
	outside := writeFile(t, t.TempDir(), "external", "must not be read")
	inside := writeFile(t, root, "inside", "safe")
	for name, target := range map[string]string{"safe": inside, "safe-relative": "inside", "external": outside, "dangling-external": outside + "-absent", "loop-a": "loop-b", "loop-b": "loop-a", "directory-cycle": "."} {
		if err := os.Symlink(target, filepath.Join(root, name)); err != nil {
			t.Fatal(err)
		}
	}
	m := testManifest(root)
	m.Files = []expectedFile{
		{DocumentID: 1, Kind: "original", Path: "safe", Checksum: digest("safe")},
		{DocumentID: 2, Kind: "original", Path: "external"},
		{DocumentID: 3, Kind: "archive", Path: "loop-a"},
		{DocumentID: 4, Kind: "original", Path: "../escape"},
		{DocumentID: 5, Kind: "original", Path: "dangling-external"},
		{DocumentID: 6, Kind: "original", Path: filepath.Join(root, "external") + "/../inside"},
	}
	r := scan(context.Background(), m)
	unsafeFiles := map[int]bool{}
	directoryCycle := false
	for _, f := range r.Findings {
		if f.Code != "unsafe_path" {
			t.Fatalf("unexpected symlink finding: %+v", f)
		}
		if f.FileIndex != nil {
			unsafeFiles[*f.FileIndex] = true
		} else if f.Path == "directory-cycle" {
			directoryCycle = true
		}
	}
	if !r.Complete || !directoryCycle || unsafeFiles[0] || !unsafeFiles[1] || !unsafeFiles[2] || !unsafeFiles[3] || !unsafeFiles[4] || !unsafeFiles[5] {
		t.Fatalf("unsafe paths not reported: %+v", r)
	}
}

func TestSymlinkedMediaRoot(t *testing.T) {
	root := t.TempDir()
	alias := filepath.Join(t.TempDir(), "media")
	if err := os.Symlink(root, alias); err != nil {
		t.Fatal(err)
	}
	writeFile(t, root, "original", "data")
	if err := os.Symlink(filepath.Join(alias, "original"), filepath.Join(root, "safe")); err != nil {
		t.Fatal(err)
	}
	m := testManifest(alias)
	m.Files = []expectedFile{{DocumentID: 1, Kind: "original", Path: filepath.Join(alias, "safe"), Checksum: digest("data")}}
	if r := scan(context.Background(), m); !r.Complete || len(r.Findings) != 0 {
		t.Fatalf("symlinked media root failed: %+v", r)
	}
}

func TestPermissions(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("permission errors require an unprivileged user")
	}
	root := t.TempDir()
	m := testManifest(root)
	for _, kind := range []string{"original", "archive", "thumbnail"} {
		path := writeFile(t, root, kind, "secret")
		if err := os.Chmod(path, 0); err != nil {
			t.Fatal(err)
		}
		m.Files = append(m.Files, expectedFile{DocumentID: 1, Kind: kind, Path: kind})
	}
	r := scan(context.Background(), m)
	if !r.Complete || len(r.Findings) != 3 {
		t.Fatalf("permission failures missing: %+v", r)
	}
	for _, f := range r.Findings {
		if f.Code != "unreadable" {
			t.Fatalf("wrong severity/code for unreadable file: %+v", f)
		}
	}
	dir := filepath.Join(root, "unreadable-directory")
	if err := os.Mkdir(dir, 0); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chmod(dir, 0700) })
	if r := scan(context.Background(), m); r.Complete {
		t.Fatal("directory permission failure must not be a complete inventory")
	}
}

type actionContext struct {
	context.Context
	calls  int
	action func()
}

func (ctx *actionContext) Err() error {
	ctx.calls++
	if ctx.calls == 2 {
		// Synchronize a concurrent writer after the first streaming read.
		done := make(chan struct{})
		go func() { ctx.action(); close(done) }()
		<-done
	}
	return nil
}

func TestChangesDuringRead(t *testing.T) {
	for _, action := range []string{"remove", "truncate", "rewrite", "replace"} {
		t.Run(action, func(t *testing.T) {
			root := t.TempDir()
			path := writeFile(t, root, "file", strings.Repeat("a", 256*1024))
			before, _ := os.Stat(path)
			r, err := os.OpenRoot(root)
			if err != nil {
				t.Fatal(err)
			}
			defer r.Close()
			ctx := &actionContext{Context: context.Background(), action: func() {
				switch action {
				case "remove":
					err = os.Remove(path)
				case "truncate":
					err = os.Truncate(path, 1)
				case "rewrite":
					err = os.WriteFile(path, []byte(strings.Repeat("b", 256*1024)), 0644)
					if err == nil {
						err = os.Chtimes(path, time.Now(), before.ModTime().Add(time.Second))
					}
				case "replace":
					other := writeFile(t, root, "replacement", strings.Repeat("a", 256*1024))
					err = os.Rename(other, path)
				}
			}}
			checksum, readErr := readChecksum(ctx, r, "file", before)
			if err != nil {
				t.Fatal(err)
			}
			if readErr == nil || checksum != "" {
				t.Fatalf("concurrent %s yielded a clean result: %s %v", action, checksum, readErr)
			}
		})
	}
}

func TestLargeFileBoundedMemory(t *testing.T) {
	root := t.TempDir()
	path := writeFile(t, root, "large", "")
	const size = 128 * 1024 * 1024
	if err := os.Truncate(path, size); err != nil {
		t.Fatal(err)
	}
	r, err := os.OpenRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	info, _ := os.Stat(path)
	var before, after runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&before)
	checksum, err := readChecksum(context.Background(), r, "large", info)
	runtime.ReadMemStats(&after)
	if err != nil || len(checksum) != 64 || after.TotalAlloc-before.TotalAlloc > 4*1024*1024 {
		t.Fatalf("unbounded read: checksum=%s err=%v allocated=%d", checksum, err, after.TotalAlloc-before.TotalAlloc)
	}
}

func TestSpecialFileDoesNotBlock(t *testing.T) {
	root := t.TempDir()
	if err := syscall.Mkfifo(filepath.Join(root, "fifo"), 0600); err != nil {
		t.Fatal(err)
	}
	m := testManifest(root)
	m.Files = []expectedFile{{DocumentID: 1, Kind: "original", Path: "fifo"}}
	if r := scan(context.Background(), m); len(r.Findings) == 0 || r.Findings[0].Code != "missing" {
		t.Fatalf("special file not rejected: %+v", r)
	}
}

func TestProtocolAndCompletion(t *testing.T) {
	m := testManifest(t.TempDir())
	valid, _ := json.Marshal(m)
	for _, data := range []string{
		"garbage", "{}", "null", string(valid) + " {}",
		strings.Replace(string(valid), `"version":1`, `"version":2`, 1),
		strings.Replace(string(valid), `"sha256"`, `"md5"`, 1),
		strings.Replace(string(valid), `"files":[]`, `"files":null`, 1),
		strings.Replace(string(valid), `"files":[]`, `"files":[{"document_id":1,"kind":"invalid","path":"a","checksum":""}]`, 1),
		strings.Replace(string(valid), `"files":[]`, `"files":[{"document_id":1,"kind":"thumbnail","path":"a"}]`, 1),
		strings.Replace(string(valid), `"files":[]`, `"files":[{"document_id":1,"kind":"thumbnail","path":"a","checksum":null}]`, 1),
		strings.Replace(string(valid), `"excluded_paths":[]`, `"excluded_paths":[null]`, 1),
		strings.Replace(string(valid), `"version":1`, `"unexpected":1,"version":1`, 1),
	} {
		if _, err := decodeManifest(strings.NewReader(data)); err == nil {
			t.Fatalf("accepted malformed manifest: %s", data)
		}
	}
	for _, scenario := range []string{"healthy", "cancelled", "missing-root"} {
		t.Run(scenario, func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			copy := m
			if scenario == "cancelled" {
				cancel()
			} else if scenario == "missing-root" {
				copy.MediaRoot = filepath.Join(m.MediaRoot, "absent")
			}
			input, _ := json.Marshal(copy)
			var output bytes.Buffer
			status := run(ctx, bytes.NewReader(input), &output)
			var result response
			if err := json.Unmarshal(output.Bytes(), &result); err != nil {
				t.Fatal(err)
			}
			if (status == 0) != (scenario == "healthy") || result.Complete != (scenario == "healthy") {
				t.Fatalf("wrong completion status: %d %+v", status, result)
			}
		})
	}
	if status := run(context.Background(), strings.NewReader("bad"), io.Discard); status != 2 {
		t.Fatal("invalid input must fail")
	}
}
