import unittest
import json
import time
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from backend.asr import ASRUnavailableError, transcribe_audio
from backend.ollama_client import OllamaClient, OllamaError, parse_ollama_json
from backend.pipeline import build_generation_payload, validate_transcript
from backend.server import AppHandler


class _OllamaErrorHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = b'{"error":"model \'llama3.1\' not found"}'
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class _SlowOllamaHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        time.sleep(0.2)
        body = b'{"message":{"content":"{}"}}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except ConnectionError:
            pass

    def log_message(self, format, *args):
        return


class _CaptureOllamaHandler(BaseHTTPRequestHandler):
    payload = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        type(self).payload = json.loads(self.rfile.read(length).decode("utf-8"))
        body = (
            b'{"message":{"content":"{'
            b'\\"internal_note\\":\\"A\\",'
            b'\\"parent_message\\":\\"B\\",'
            b'\\"history_update\\":\\"C\\",'
            b'\\"qa_suggestions\\":[\\"D\\"]'
            b'}"}}'
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class PipelineTests(unittest.TestCase):
    def test_validate_transcript_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            validate_transcript("   ")

    def test_build_generation_payload_includes_history_and_transcript(self):
        payload = build_generation_payload(
            transcript="Занимались чтением слогов и домашним заданием.",
            child={"display_name": "Ребёнок А", "goals": ["слоги"], "sessions": [{"history_update": "Лучше удерживает внимание."}]},
        )

        messages = "\n".join(message["content"] for message in payload["messages"])
        self.assertIn("Занимались чтением слогов", messages)
        self.assertIn("Лучше удерживает внимание", messages)
        self.assertIn("parent_message", messages)

    def test_parse_ollama_json_accepts_plain_json_content(self):
        parsed = parse_ollama_json(
            {
                "message": {
                    "content": '{"internal_note":"A","parent_message":"B","history_update":"C","qa_suggestions":["D"]}'
                }
            }
        )

        self.assertEqual(parsed["internal_note"], "A")
        self.assertEqual(parsed["qa_suggestions"], ["D"])

    def test_parse_ollama_json_rejects_missing_required_fields(self):
        with self.assertRaises(OllamaError):
            parse_ollama_json({"message": {"content": '{"internal_note":"A"}'}})

    def test_ollama_unavailable_maps_to_named_error(self):
        client = OllamaClient(base_url="http://127.0.0.1:1", timeout_seconds=0.1)

        with self.assertRaises(OllamaError):
            client.list_models()

    def test_ollama_http_error_preserves_model_not_found_message(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaErrorHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = OllamaClient(base_url=f"http://127.0.0.1:{server.server_port}", timeout_seconds=1)

        try:
            with self.assertRaisesRegex(OllamaError, "model 'llama3.1' not found"):
                client.chat_json([{"role": "user", "content": "hello"}])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

    def test_ollama_timeout_error_names_timeout_seconds(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _SlowOllamaHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = OllamaClient(base_url=f"http://127.0.0.1:{server.server_port}", timeout_seconds=0.01)

        try:
            with self.assertRaisesRegex(OllamaError, "timed out after 0.01 seconds"):
                client.chat_json([{"role": "user", "content": "hello"}])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

    def test_ollama_chat_disables_thinking_and_limits_prediction(self):
        _CaptureOllamaHandler.payload = {}
        server = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureOllamaHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = OllamaClient(
            base_url=f"http://127.0.0.1:{server.server_port}",
            timeout_seconds=1,
            think=False,
            num_predict=700,
        )

        try:
            client.chat_json([{"role": "user", "content": "hello"}])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

        self.assertEqual(_CaptureOllamaHandler.payload["think"], False)
        self.assertEqual(_CaptureOllamaHandler.payload["options"]["num_predict"], 700)

    def test_server_ollama_client_uses_timeout_env(self):
        handler = AppHandler.__new__(AppHandler)

        with patch.dict("os.environ", {"OLLAMA_TIMEOUT_SECONDS": "180"}, clear=False):
            client = handler._ollama_client()

        self.assertEqual(client.timeout_seconds, 180)

    def test_asr_unavailable_has_recoverable_error(self):
        with self.assertRaises(ASRUnavailableError):
            transcribe_audio(b"not-a-real-audio-file", model_name="__missing_test_model__")


if __name__ == "__main__":
    unittest.main()
