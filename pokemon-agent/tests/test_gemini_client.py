"""Tests for gemini_client.py — Gemini LLM backend for Pokemon agent.

Tests the GeminiClient that implements LLMClient protocol using
google-generativeai SDK. Mocks the API to avoid real API calls.
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agent import LLMResponse, ToolUse


class TestGeminiClientImport(unittest.TestCase):
    """Test that GeminiClient can be imported."""

    def test_import(self):
        from gemini_client import GeminiClient
        self.assertTrue(callable(GeminiClient))

    def test_implements_protocol(self):
        """GeminiClient should have create_message method matching LLMClient."""
        from gemini_client import GeminiClient
        self.assertTrue(hasattr(GeminiClient, "create_message"))


class TestGeminiClientInit(unittest.TestCase):
    """Test GeminiClient initialization."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"})
    @patch("gemini_client.genai")
    def test_init_with_api_key(self, mock_genai):
        from gemini_client import GeminiClient
        client = GeminiClient()
        mock_genai.configure.assert_called_once_with(api_key="test-key-123")

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "google-key-456"}, clear=True)
    @patch("gemini_client.genai")
    def test_init_with_google_api_key(self, mock_genai):
        """Falls back to GOOGLE_API_KEY if GEMINI_API_KEY not set."""
        os.environ.pop("GEMINI_API_KEY", None)
        from gemini_client import GeminiClient
        client = GeminiClient()
        mock_genai.configure.assert_called_once_with(api_key="google-key-456")

    @patch.dict(os.environ, {}, clear=True)
    @patch("gemini_client.genai")
    def test_init_no_key_raises(self, mock_genai):
        """Should raise ValueError if no API key is set."""
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)
        from gemini_client import GeminiClient
        with self.assertRaises(ValueError):
            GeminiClient()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    @patch("gemini_client.genai")
    def test_custom_model(self, mock_genai):
        from gemini_client import GeminiClient
        client = GeminiClient(model_name="gemini-2.5-pro")
        self.assertEqual(client.model_name, "gemini-2.5-pro")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    @patch("gemini_client.genai")
    def test_default_model_is_flash(self, mock_genai):
        from gemini_client import GeminiClient
        client = GeminiClient()
        self.assertIn("flash", client.model_name.lower())


class TestGeminiClientCreateMessage(unittest.TestCase):
    """Test create_message translates between Anthropic-style and Gemini API."""

    def _make_client(self, mock_genai):
        """Create a GeminiClient with mocked genai."""
        from gemini_client import GeminiClient
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("gemini_client.genai", mock_genai):
                client = GeminiClient()
        return client

    @patch("gemini_client.genai")
    def test_text_response(self, mock_genai):
        """Should return LLMResponse with text from Gemini."""
        # Mock Gemini response
        mock_part = MagicMock()
        mock_part.text = "I'll press A to continue."
        mock_part.function_call = None
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        client = self._make_client(mock_genai)
        result = client.create_message(
            model="gemini-2.5-flash",
            max_tokens=1024,
            system="You are a Pokemon player.",
            messages=[{"role": "user", "content": "What do you see?"}],
            tools=[],
            temperature=0.0,
        )

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "I'll press A to continue.")
        self.assertEqual(result.input_tokens, 100)
        self.assertEqual(result.output_tokens, 50)

    @patch("gemini_client.genai")
    def test_tool_call_response(self, mock_genai):
        """Should parse Gemini function_call into ToolUse."""
        # Mock a function call response
        mock_fc = MagicMock()
        mock_fc.name = "press_buttons"
        mock_fc.args = {"buttons": ["a", "b"]}

        mock_part = MagicMock()
        mock_part.text = None
        mock_part.function_call = mock_fc

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]
        mock_response.usage_metadata.prompt_token_count = 200
        mock_response.usage_metadata.candidates_token_count = 30

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        client = self._make_client(mock_genai)
        result = client.create_message(
            model="gemini-2.5-flash",
            max_tokens=1024,
            system="Play Pokemon.",
            messages=[{"role": "user", "content": "Battle!"}],
            tools=[{"name": "press_buttons", "description": "Press buttons",
                    "input_schema": {"type": "object", "properties": {"buttons": {"type": "array"}}}}],
            temperature=0.0,
        )

        self.assertEqual(len(result.tool_uses), 1)
        self.assertEqual(result.tool_uses[0].name, "press_buttons")
        self.assertEqual(result.tool_uses[0].input, {"buttons": ["a", "b"]})

    @patch("gemini_client.genai")
    def test_tool_call_coerces_integer_like_numbers(self, mock_genai):
        """Gemini tool args should normalize 3.0 -> 3 for integer fields."""
        mock_fc = MagicMock()
        mock_fc.name = "navigate_to"
        mock_fc.args = {"x": 7.0, "y": 0.0}

        mock_part = MagicMock()
        mock_part.text = None
        mock_part.function_call = mock_fc

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]
        mock_response.usage_metadata.prompt_token_count = 120
        mock_response.usage_metadata.candidates_token_count = 25

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        client = self._make_client(mock_genai)
        result = client.create_message(
            model="gemini-2.5-flash",
            max_tokens=1024,
            system="Play Pokemon.",
            messages=[{"role": "user", "content": "Move!"}],
            tools=[{"name": "navigate_to", "description": "Move to coordinates",
                    "input_schema": {"type": "object", "properties": {
                        "x": {"type": "integer"}, "y": {"type": "integer"}}}}],
            temperature=0.0,
        )

        self.assertEqual(result.tool_uses[0].input, {"x": 7, "y": 0})

    @patch("gemini_client.genai")
    def test_mixed_text_and_tool_response(self, mock_genai):
        """Should handle responses with both text and tool calls."""
        mock_text_part = MagicMock()
        mock_text_part.text = "Let me press A."
        mock_text_part.function_call = None

        mock_fc = MagicMock()
        mock_fc.name = "press_buttons"
        mock_fc.args = {"buttons": ["a"]}
        mock_tool_part = MagicMock()
        mock_tool_part.text = None
        mock_tool_part.function_call = mock_fc

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_text_part, mock_tool_part]
        mock_response.usage_metadata.prompt_token_count = 150
        mock_response.usage_metadata.candidates_token_count = 40

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        client = self._make_client(mock_genai)
        result = client.create_message(
            model="gemini-2.5-flash",
            max_tokens=1024,
            system="Play Pokemon.",
            messages=[],
            tools=[],
            temperature=0.0,
        )

        self.assertEqual(result.text, "Let me press A.")
        self.assertEqual(len(result.tool_uses), 1)


class TestToolConversion(unittest.TestCase):
    """Test Anthropic tool format -> Gemini function declaration conversion."""

    def test_convert_tool_format(self):
        from gemini_client import _anthropic_tool_to_gemini
        anthropic_tool = {
            "name": "press_buttons",
            "description": "Press one or more buttons on the Game Boy.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "buttons": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Buttons to press",
                    }
                },
                "required": ["buttons"],
            },
        }
        result = _anthropic_tool_to_gemini(anthropic_tool)
        self.assertEqual(result["name"], "press_buttons")
        self.assertEqual(result["description"], "Press one or more buttons on the Game Boy.")
        self.assertIn("parameters", result)
        self.assertEqual(result["parameters"]["type_"], "OBJECT")
        self.assertNotIn("type", result["parameters"])
        self.assertEqual(
            result["parameters"]["properties"]["buttons"]["type_"],
            "ARRAY",
        )
        self.assertEqual(
            result["parameters"]["properties"]["buttons"]["items"]["type_"],
            "STRING",
        )

    def test_convert_nested_tool_schema(self):
        from gemini_client import _anthropic_tool_to_gemini
        anthropic_tool = {
            "name": "update_objectives",
            "description": "Update quest log.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "objectives": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["active", "completed"],
                                    "default": "active",
                                },
                            },
                            "required": ["description"],
                        },
                    },
                },
                "required": ["objectives"],
            },
        }
        result = _anthropic_tool_to_gemini(anthropic_tool)
        objective_schema = result["parameters"]["properties"]["objectives"]["items"]
        self.assertEqual(objective_schema["type_"], "OBJECT")
        self.assertEqual(
            objective_schema["properties"]["description"]["type_"],
            "STRING",
        )
        self.assertEqual(
            objective_schema["properties"]["status"]["enum"],
            ["active", "completed"],
        )
        self.assertNotIn("default", objective_schema["properties"]["status"])

    def test_convert_empty_tools(self):
        from gemini_client import _anthropic_tools_to_gemini
        self.assertEqual(_anthropic_tools_to_gemini([]), [])
        self.assertEqual(_anthropic_tools_to_gemini(None), [])


class TestMessageConversion(unittest.TestCase):
    """Test Anthropic message format -> Gemini content conversion."""

    def test_convert_messages_with_tool_history(self):
        from gemini_client import _anthropic_messages_to_gemini

        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Going to press A."},
                    {
                        "type": "tool_use",
                        "id": "tool-1",
                        "name": "press_buttons",
                        "input": {"buttons": ["a"]},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-1",
                        "content": json.dumps({"pressed": ["a"], "count": 1}),
                    },
                ],
            },
        ]

        result = _anthropic_messages_to_gemini(messages)

        self.assertEqual(result[0]["role"], "model")
        self.assertEqual(result[0]["parts"][0]["text"], "Going to press A.")
        self.assertEqual(
            result[0]["parts"][1]["function_call"]["name"],
            "press_buttons",
        )
        self.assertEqual(
            result[0]["parts"][1]["function_call"]["args"],
            {"buttons": ["a"]},
        )
        self.assertEqual(
            result[1]["parts"][0]["function_response"]["name"],
            "press_buttons",
        )
        self.assertEqual(
            result[1]["parts"][0]["function_response"]["response"],
            {"pressed": ["a"], "count": 1},
        )


class TestArgNormalization(unittest.TestCase):
    """Test normalization of Gemini function-call args."""

    def test_sequence_like_values_become_lists(self):
        from gemini_client import _normalize_tool_args

        result = _normalize_tool_args({
            "buttons": ("left", "right"),
            "nested": {"coords": (7.0, 0.0)},
        })

        self.assertEqual(result["buttons"], ["left", "right"])
        self.assertEqual(result["nested"]["coords"], [7, 0])


if __name__ == "__main__":
    unittest.main()
