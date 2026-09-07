"""Deterministic native-AI test double; never contacts an inference provider."""

import hashlib
import json
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer

PROPOSAL = {
    "title": "Synthetic review example",
    "tags": ["Fixture"],
    "correspondents": ["Example sender"],
    "document_types": ["Example document"],
    "storage_paths": [],
    "dates": ["2026-01-02"],
}
STATE = {"native_requests": 0, "provider_requests": 0, "applied": {}}
STATE_LOCK = threading.Lock()


def provider_reply(request):
    if request.get("protocol_version") != 1:
        raise ValueError("Unsupported protocol")
    if request.get("event") == "suggestions.applied":
        event_id = request["event_id"]
        with STATE_LOCK:
            STATE["applied"][event_id] = request
        return {"event_id": event_id}
    if request.get("event") != "suggestions.requested":
        raise ValueError("Unexpected event")
    context = {
        key: request[key]
        for key in (
            "document",
            "requester_id",
            "output_language",
            "taxonomy",
            "classic_suggestions",
        )
    }
    digest = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
    if digest != request["context_id"] or not request["document"]["id"]:
        raise ValueError("Invalid document context")
    if (
        not request["document"]["content"]
        or not request["document"]["content_version"]["id"]
    ):
        raise ValueError("Missing source content or version")
    suggestions = {"title": PROPOSAL["title"], "dates": PROPOSAL["dates"]}
    for key in ("tags", "correspondents", "document_types", "storage_paths"):
        suggestions[key] = {
            "existing_ids": [
                item["id"]
                for item in request["taxonomy"][key]
                if item["name"] in PROPOSAL[key]
            ],
            "new_names": [],
        }
    with STATE_LOCK:
        STATE["provider_requests"] += 1
    return {
        "protocol_version": 1,
        "request_id": request["request_id"],
        "context_id": request["context_id"],
        "suggestions": suggestions,
    }


def completion(request):
    """Return the tool-call shape used by the upstream classification client."""
    if request.get("model") != "synthetic-fixture" or request.get("stream"):
        raise ValueError("Only non-streaming synthetic-fixture requests are supported")
    names = [tool.get("function", {}).get("name") for tool in request.get("tools", [])]
    if "DocumentClassifierSchema" not in names:
        raise ValueError("Expected the native DocumentClassifierSchema tool")
    return {
        "id": "synthetic-completion",
        "object": "chat.completion",
        "created": 0,
        "model": "synthetic-fixture",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "synthetic-tool-call",
                            "type": "function",
                            "function": {
                                "name": "DocumentClassifierSchema",
                                "arguments": json.dumps(PROPOSAL),
                            },
                        },
                    ],
                },
            },
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        # Request bodies and headers never belong in test logs.
        pass

    def respond(self, status, value):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"mode": "synthetic-fixture"})
        elif self.path == "/test-state":
            with STATE_LOCK:
                self.respond(200, STATE)
        else:
            self.respond(404, {"error": "Unknown test endpoint"})

    def do_POST(self):
        if self.path not in {"/v1/chat/completions", "/suggestions"}:
            self.respond(404, {"error": "Unknown test endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1_048_576:
                raise ValueError("Invalid request size")
            request = json.loads(self.rfile.read(length))
            if self.path == "/suggestions":
                if (
                    self.headers.get("Authorization")
                    != "Bearer synthetic-provider-only"
                ):
                    self.respond(401, {"error": "Invalid synthetic provider key"})
                    return
                self.respond(200, provider_reply(request))
            else:
                with STATE_LOCK:
                    STATE["native_requests"] += 1
                self.respond(200, completion(request))
        except (ValueError, TypeError, AttributeError, KeyError):
            self.respond(400, {"error": "Invalid synthetic completion request"})


if __name__ == "__main__":
    if sys.argv[1:] == ["--probe"]:
        with urllib.request.urlopen(
            "http://127.0.0.1:8080/test-state", timeout=5,
        ) as response:
            print(response.read().decode())  # noqa: T201
    else:
        ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
