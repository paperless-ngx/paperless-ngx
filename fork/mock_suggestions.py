"""Deterministic native-AI test double; never contacts an inference provider."""

import json
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
        else:
            self.respond(404, {"error": "Unknown test endpoint"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.respond(404, {"error": "Unknown test endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1_048_576:
                raise ValueError("Invalid request size")
            request = json.loads(self.rfile.read(length))
            self.respond(200, completion(request))
        except (ValueError, TypeError, AttributeError):
            self.respond(400, {"error": "Invalid synthetic completion request"})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
