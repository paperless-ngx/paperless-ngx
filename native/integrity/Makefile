PREFIX ?= $(HOME)/.local
GO ?= go

.PHONY: build install test clean

build:
	CGO_ENABLED=0 $(GO) build -trimpath -ldflags="-s -w -buildid=" -o paperless-integrity-scanner .

install: build
	install -d "$(PREFIX)/bin"
	install -m 755 paperless-integrity-scanner "$(PREFIX)/bin/paperless-integrity-scanner"

test:
	$(GO) test -race ./...
	$(GO) vet ./...
	test -z "$$($(GO) fmt ./...)"

clean:
	rm -f paperless-integrity-scanner
