package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
)

const protocolVersion = 1

type expectedFile struct {
	DocumentID int    `json:"document_id"`
	Kind       string `json:"kind"`
	Path       string `json:"path"`
	Checksum   string `json:"checksum"`
}

type manifest struct {
	Version          int            `json:"version"`
	MediaRoot        string         `json:"media_root"`
	Algorithm        string         `json:"checksum_algorithm"`
	Files            []expectedFile `json:"files"`
	IgnoredFilenames []string       `json:"ignored_filenames"`
	ExcludedPaths    []string       `json:"excluded_paths"`
}

type finding struct {
	Code           string `json:"code"`
	FileIndex      *int   `json:"file_index"`
	Path           string `json:"path"`
	Detail         string `json:"detail"`
	ActualChecksum string `json:"actual_checksum"`
}

type response struct {
	Version      int       `json:"version"`
	Complete     bool      `json:"complete"`
	CheckedFiles int       `json:"checked_files"`
	Findings     []finding `json:"findings"`
}

func decodeManifest(r io.Reader) (manifest, error) {
	var m manifest
	var raw json.RawMessage
	d := json.NewDecoder(r)
	if err := d.Decode(&raw); err != nil {
		return m, err
	}
	var extra any
	if err := d.Decode(&extra); err != io.EOF {
		return m, errors.New("expected exactly one JSON manifest")
	}
	if err := requiredFields(raw, "version", "media_root", "checksum_algorithm", "files", "ignored_filenames", "excluded_paths"); err != nil {
		return m, err
	}
	d = json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	if err := d.Decode(&m); err != nil {
		return m, err
	}
	var object map[string]json.RawMessage
	_ = json.Unmarshal(raw, &object)
	var files []json.RawMessage
	_ = json.Unmarshal(object["files"], &files)
	for _, file := range files {
		if err := requiredFields(file, "document_id", "kind", "path", "checksum"); err != nil {
			return m, err
		}
	}
	if m.Version != protocolVersion || m.Algorithm != "sha256" || !filepath.IsAbs(m.MediaRoot) || m.Files == nil || m.IgnoredFilenames == nil || m.ExcludedPaths == nil {
		return m, errors.New("invalid version, algorithm, root or arrays")
	}
	for _, f := range m.Files {
		if f.DocumentID <= 0 || f.Path == "" || (f.Kind != "original" && f.Kind != "archive" && f.Kind != "thumbnail") {
			return m, errors.New("invalid expected file")
		}
	}
	for _, name := range m.IgnoredFilenames {
		if name == "" || filepath.Base(name) != name {
			return m, errors.New("ignored filenames must be basenames")
		}
	}
	for _, path := range m.ExcludedPaths {
		if path == "" {
			return m, errors.New("excluded paths must not be empty")
		}
	}
	return m, nil
}

func requiredFields(raw json.RawMessage, names ...string) error {
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil {
		return err
	}
	for _, name := range names {
		value, exists := object[name]
		if !exists || bytes.Equal(bytes.TrimSpace(value), []byte("null")) {
			return fmt.Errorf("missing or null field %s", name)
		}
	}
	return nil
}

type scanner struct {
	ctx            context.Context
	root           *os.Root
	base           string
	configuredBase string
	result         response
	present        map[string]string
}

func (s *scanner) add(code string, index *int, path string, err error) {
	detail := ""
	if err != nil {
		detail = err.Error()
	}
	s.result.Findings = append(s.result.Findings, finding{Code: code, FileIndex: index, Path: path, Detail: detail})
	if code == "scan_error" {
		s.result.Complete = false
	}
}

func relativePath(base, path string) (string, error) {
	if path == base {
		return ".", nil
	}
	prefix := strings.TrimSuffix(base, string(filepath.Separator)) + string(filepath.Separator)
	if !strings.HasPrefix(path, prefix) {
		return "", errors.New("path is outside media root")
	}
	return strings.TrimPrefix(path, prefix), nil
}

// Canonical names deduplicate internal file aliases. All actual file reads use
// os.Root, which also enforces containment if a symlink changes after this check.
func (s *scanner) canonical(path string) (string, error) {
	if filepath.IsAbs(path) {
		var err error
		path, err = relativePath(s.configuredBase, path)
		if err != nil {
			return "", err
		}
	}
	if !filepath.IsLocal(path) {
		return "", errors.New("path is outside media root")
	}
	components := strings.Split(path, string(filepath.Separator))
	resolved := "."
	links := 0
	for len(components) > 0 {
		component := components[0]
		components = components[1:]
		if component == "" || component == "." {
			continue
		}
		candidate := filepath.Join(resolved, component)
		if !filepath.IsLocal(candidate) {
			return "", errors.New("symlink is outside media root")
		}
		info, err := s.root.Lstat(candidate)
		if err != nil {
			return "", err
		}
		if info.Mode()&os.ModeSymlink == 0 {
			if len(components) > 0 && !info.IsDir() {
				return "", &fs.PathError{Op: "stat", Path: candidate, Err: syscall.ENOTDIR}
			}
			resolved = candidate
			continue
		}
		links++
		if links > 255 {
			return "", syscall.ELOOP
		}
		target, err := s.root.Readlink(candidate)
		if err != nil {
			return "", err
		}
		if filepath.IsAbs(target) {
			relative, relErr := relativePath(s.base, target)
			if relErr != nil || !filepath.IsLocal(relative) {
				relative, relErr = relativePath(s.configuredBase, target)
			}
			if relErr != nil || !filepath.IsLocal(relative) {
				return "", errors.New("symlink is outside media root")
			}
			target = relative
			resolved = "."
		}
		components = append(strings.Split(target, string(filepath.Separator)), components...)
	}
	return resolved, nil
}

func unsafe(err error) bool {
	return errors.Is(err, syscall.ELOOP) || strings.Contains(err.Error(), "outside media root") || strings.Contains(err.Error(), "escapes from parent") || strings.Contains(err.Error(), "too many links")
}

func unchanged(a, b fs.FileInfo) bool {
	if !os.SameFile(a, b) || a.Size() != b.Size() || a.ModTime() != b.ModTime() || a.Mode() != b.Mode() {
		return false
	}
	left, leftOK := a.Sys().(*syscall.Stat_t)
	right, rightOK := b.Sys().(*syscall.Stat_t)
	return !leftOK || !rightOK || left.Ctim == right.Ctim
}

func readChecksum(ctx context.Context, root *os.Root, path string, before fs.FileInfo) (string, error) {
	f, err := root.OpenFile(path, os.O_RDONLY|syscall.O_NONBLOCK, 0)
	if err != nil {
		return "", err
	}
	defer f.Close()
	opened, err := f.Stat()
	if err != nil {
		return "", err
	}
	if !opened.Mode().IsRegular() || !unchanged(before, opened) {
		return "", errors.New("file changed before reading")
	}
	h := sha256.New()
	buffer := make([]byte, 64*1024)
	var total int64
	for {
		if err := ctx.Err(); err != nil {
			return "", err
		}
		n, err := f.Read(buffer)
		total += int64(n)
		_, _ = h.Write(buffer[:n])
		if err == io.EOF {
			break
		}
		if err != nil {
			return "", err
		}
	}
	after, err := f.Stat()
	if err != nil {
		return "", err
	}
	current, err := root.Stat(path)
	if err != nil {
		return "", err
	}
	if total != before.Size() || !unchanged(before, after) || !unchanged(before, current) {
		return "", errors.New("file changed during reading")
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func (s *scanner) checkFile(index int, f expectedFile) {
	path, err := s.canonical(f.Path)
	if err != nil {
		code := "unreadable"
		if unsafe(err) {
			code = "unsafe_path"
		} else if errors.Is(err, fs.ErrNotExist) || errors.Is(err, syscall.ENOTDIR) {
			code = "missing"
		}
		s.add(code, &index, f.Path, err)
		return
	}
	info, err := s.root.Stat(path)
	if err != nil {
		code := "unreadable"
		if unsafe(err) {
			code = "unsafe_path"
		} else if errors.Is(err, fs.ErrNotExist) || errors.Is(err, syscall.ENOTDIR) {
			code = "missing"
		}
		s.add(code, &index, f.Path, err)
		return
	}
	if !info.Mode().IsRegular() {
		s.add("missing", &index, f.Path, errors.New("not a regular file"))
		return
	}
	delete(s.present, path)
	checksum, err := readChecksum(s.ctx, s.root, path, info)
	if err == nil {
		current, resolveErr := s.canonical(f.Path)
		if resolveErr != nil {
			err = resolveErr
		} else if current != path {
			err = errors.New("file symlink changed during reading")
		}
	}
	if err != nil {
		code := "unreadable"
		if unsafe(err) {
			code = "unsafe_path"
		}
		s.add(code, &index, f.Path, err)
	} else if f.Kind != "thumbnail" && checksum != f.Checksum {
		s.result.Findings = append(s.result.Findings, finding{Code: "checksum_mismatch", FileIndex: &index, Path: f.Path, ActualChecksum: checksum})
	}
}

func scan(ctx context.Context, m manifest) response {
	s := scanner{ctx: ctx, result: response{Version: protocolVersion, Complete: true, Findings: []finding{}}, present: map[string]string{}}
	base, err := filepath.EvalSymlinks(m.MediaRoot)
	if err != nil {
		s.add("scan_error", nil, m.MediaRoot, err)
		return s.result
	}
	s.base = base
	s.configuredBase = filepath.Clean(m.MediaRoot)
	s.root, err = os.OpenRoot(base)
	if err != nil {
		s.add("scan_error", nil, base, err)
		return s.result
	}
	defer s.root.Close()
	ignored := map[string]bool{}
	for _, name := range m.IgnoredFilenames {
		ignored[name] = true
	}
	excluded := map[string]bool{}
	for _, path := range m.ExcludedPaths {
		canonical, err := s.canonical(path)
		if err == nil {
			excluded[canonical] = true
		} else if !errors.Is(err, fs.ErrNotExist) {
			code := "scan_error"
			if unsafe(err) {
				code = "unsafe_path"
			}
			s.add(code, nil, path, err)
		}
	}
	err = fs.WalkDir(s.root.FS(), ".", func(path string, entry fs.DirEntry, walkErr error) error {
		if err := ctx.Err(); err != nil {
			return err
		}
		if walkErr != nil {
			s.add("scan_error", nil, path, walkErr)
			return nil
		}
		if entry.IsDir() || ignored[entry.Name()] {
			return nil
		}
		canonical, err := s.canonical(path)
		if err != nil {
			code := "scan_error"
			if unsafe(err) {
				code = "unsafe_path"
			}
			s.add(code, nil, path, err)
			return nil
		}
		info, err := s.root.Stat(canonical)
		if err != nil {
			s.add("scan_error", nil, path, err)
		} else if info.IsDir() && entry.Type()&os.ModeSymlink != 0 && (canonical == "." || filepath.Dir(path) == canonical || strings.HasPrefix(filepath.Dir(path), canonical+string(filepath.Separator))) {
			s.add("unsafe_path", nil, path, errors.New("directory symlink creates a traversal cycle"))
		} else if !info.IsDir() && !excluded[canonical] {
			s.present[canonical] = filepath.Join(base, canonical)
		}
		return nil
	})
	if err != nil {
		s.add("scan_error", nil, base, err)
	}
	for index, f := range m.Files {
		if err := ctx.Err(); err != nil {
			s.add("scan_error", nil, base, err)
			return s.result
		}
		s.checkFile(index, f)
		s.result.CheckedFiles++
	}
	for path, absolute := range s.present {
		if _, err := s.root.Stat(path); err != nil {
			s.add("scan_error", nil, path, err)
		} else {
			s.add("orphan", nil, absolute, nil)
		}
	}
	if err := ctx.Err(); err != nil {
		s.add("scan_error", nil, base, err)
	}
	return s.result
}

func run(ctx context.Context, input io.Reader, output io.Writer) int {
	m, err := decodeManifest(input)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Invalid integrity scanner manifest:", err)
		return 2
	}
	result := scan(ctx, m)
	if err := json.NewEncoder(output).Encode(result); err != nil {
		fmt.Fprintln(os.Stderr, "Cannot write integrity scanner response:", err)
		return 2
	}
	if !result.Complete {
		return 2
	}
	return 0
}

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	status := make(chan int, 1)
	go func() { status <- run(ctx, os.Stdin, os.Stdout) }()
	select {
	case code := <-status:
		os.Exit(code)
	case <-ctx.Done():
		fmt.Fprintln(os.Stderr, "Integrity scanner interrupted; scan incomplete:", ctx.Err())
		os.Exit(2)
	}
}
