import unittest

from backend.asr import ASRUnavailableError, transcribe_audio
from backend.ollama_client import OllamaClient, OllamaError, parse_ollama_json
from backend.pipeline import build_generation_payload, validate_transcript


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

    def test_asr_unavailable_has_recoverable_error(self):
        with self.assertRaises(ASRUnavailableError):
            transcribe_audio(b"not-a-real-audio-file", model_name="__missing_test_model__")


if __name__ == "__main__":
    unittest.main()
