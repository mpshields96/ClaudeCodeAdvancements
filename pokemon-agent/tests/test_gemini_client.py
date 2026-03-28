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

    def test_convert_empty_tools(self):
        from gemini_client import _anthropic_tools_to_gemini
        self.assertEqual(_anthropic_tools_to_gemini([]), [])
        self.assertEqual(_anthropic_tools_to_gemini(None), [])


if __name__ == "__main__":
    unittest.main()
