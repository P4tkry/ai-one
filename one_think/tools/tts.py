"""
Edge TTS Tool - Real text-to-speech implementation using Microsoft Edge TTS.
Speech synthesis with high-quality Microsoft voices and full multilingual support.

Recommended installation:
    pip install edge-tts

Python import:
    import edge_tts
"""

from typing import Dict, Any, Optional, Literal, List, Tuple
from pydantic import BaseModel, Field
import os
import time
import uuid
import asyncio
from pathlib import Path

from one_think.tools.base import Tool, ToolResponse
from one_think.utils.output_manager import get_output_path

# Try to import Edge TTS, fallback gracefully
try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


class EdgeTTSTool(Tool):
    """Edge TTS tool with Microsoft Speech Services."""

    name = "tts"
    description = "Edge TTS - text to speech with Microsoft voices"
    version = "2.0.0"

    class Input(BaseModel):
        """Input parameters for TTS operations."""
        operation: Literal["list_voices", "synthesize", "get_voice_info"] = Field(
            description="Operation to perform"
        )

        # Common
        voice: Optional[str] = Field(
            default=None,
            description=(
                "Voice name, e.g. en-US-AriaNeural, en-GB-SoniaNeural, "
                "pl-PL-MarekNeural, fr-FR-DeniseNeural"
            )
        )

        # Text synthesis
        text: Optional[str] = Field(
            default=None,
            description="Text to synthesize (required for synthesize)"
        )

        file_path: Optional[str] = Field(
            default=None,
            description="Output WAV file path. If omitted, auto-generated in outputs/"
        )

        # Filtering
        language: Optional[str] = Field(
            default=None,
            description="Filter voices by language code (e.g., 'en-US', 'pl-PL', 'fr-FR')"
        )

        gender: Optional[Literal["Male", "Female"]] = Field(
            default=None,
            description="Filter voices by gender"
        )

        max_results: Optional[int] = Field(
            default=50,
            description="Maximum number of results for list_voices (1-500)"
        )

    class Output(BaseModel):
        """Output structure for TTS operations."""
        operation: str = Field(description="Operation performed")
        success: bool = Field(description="Whether operation succeeded")
        voices: Optional[List[Dict[str, str]]] = Field(
            default=None,
            description="List of available voices with metadata"
        )
        output_file: Optional[str] = Field(
            default=None,
            description="Path to generated audio file"
        )
        voice_info: Optional[Dict[str, str]] = Field(
            default=None,
            description="Detailed information about a specific voice"
        )
        execution_time_ms: float = Field(
            description="Execution time in milliseconds"
        )
        details: Optional[Dict[str, Any]] = Field(
            default=None,
            description="Additional metadata"
        )

    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute TTS operation with JSON response."""

        if params.get("help"):
            return self._create_success_response(
                result={"help": self.get_help()},
                request_id=request_id
            )

        if not TTS_AVAILABLE:
            return self._create_error_response(
                "InstallationError",
                "Edge TTS library not installed. Install with: pip install edge-tts",
                request_id=request_id
            )

        error = self.validate_required_params(params, required=["operation"])
        if error:
            return error

        operation = params["operation"]

        if operation == "list_voices":
            return self._list_voices(params, request_id)
        elif operation == "synthesize":
            return self._synthesize(params, request_id)
        elif operation == "get_voice_info":
            return self._get_voice_info(params, request_id)
        else:
            return self._create_error_response(
                "ValidationError",
                f"Unknown operation: {operation}. Supported: list_voices, synthesize, get_voice_info",
                request_id=request_id
            )

    def _list_voices(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """List available Edge TTS voices."""
        start_time = time.time()

        try:
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                voices = loop.run_until_complete(edge_tts.list_voices())
            finally:
                loop.close()

            # Filter by language if specified
            language_filter = params.get("language")
            if language_filter:
                voices = [v for v in voices if v["Locale"].startswith(language_filter)]

            # Filter by gender if specified
            gender_filter = params.get("gender")
            if gender_filter:
                voices = [v for v in voices if v["Gender"] == gender_filter]

            # Limit results
            max_results = params.get("max_results", 50)
            if max_results and len(voices) > max_results:
                voices = voices[:max_results]

            # Format voice data
            formatted_voices = []
            for voice in voices:
                voice_tag = voice.get("VoiceTag", {})
                formatted_voices.append({
                    "name": voice["ShortName"],  # Use ShortName instead of Name
                    "display_name": voice["FriendlyName"],  # Use FriendlyName instead of DisplayName
                    "locale": voice["Locale"],
                    "gender": voice["Gender"],
                    "content_categories": ", ".join(voice_tag.get("ContentCategories", [])),
                    "voice_personalities": ", ".join(voice_tag.get("VoicePersonalities", [])),
                    "status": voice.get("Status", ""),
                    "suggested_codec": voice.get("SuggestedCodec", "")
                })

            execution_time = (time.time() - start_time) * 1000

            return self._create_success_response(
                result={
                    "operation": "list_voices",
                    "success": True,
                    "voices": formatted_voices,
                    "count": len(formatted_voices),
                    "execution_time_ms": execution_time
                },
                request_id=request_id
            )

        except Exception as e:
            return self._create_error_response(
                "TTSError",
                f"Failed to list voices: {e}",
                request_id=request_id
            )

    def _synthesize(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Synthesize text to speech."""
        start_time = time.time()

        # Validate required parameters
        text = params.get("text")
        if not text:
            return self._create_error_response(
                "ValidationError",
                "Parameter 'text' is required for synthesize operation",
                request_id=request_id
            )

        voice = params.get("voice", "en-US-AriaNeural")  # Default voice

        # Generate output file path using OutputManager
        file_path = params.get("file_path")
        if not file_path:
            # Use universal output manager for consistent naming
            file_path = get_output_path("tts", "wav", subdirectory="audio")
        else:
            file_path = Path(file_path)

        # Ensure output directory exists  
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Run async synthesis
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                communicate = edge_tts.Communicate(text, voice)
                loop.run_until_complete(communicate.save(str(file_path)))
            finally:
                loop.close()

            execution_time = (time.time() - start_time) * 1000

            return self._create_success_response(
                result={
                    "operation": "synthesize",
                    "success": True,
                    "output_file": str(file_path),
                    "voice": voice,
                    "text_length": len(text),
                    "execution_time_ms": execution_time
                },
                request_id=request_id
            )

        except Exception as e:
            return self._create_error_response(
                "TTSError",
                f"Synthesis failed: {e}",
                request_id=request_id
            )

    def _get_voice_info(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Get detailed information about a specific voice."""
        start_time = time.time()

        voice_name = params.get("voice")
        if not voice_name:
            return self._create_error_response(
                "ValidationError",
                "Parameter 'voice' is required for get_voice_info operation",
                request_id=request_id
            )

        try:
            # Get all voices and find the specified one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                voices = loop.run_until_complete(edge_tts.list_voices())
            finally:
                loop.close()

            # Find matching voice
            voice_info = None
            for voice in voices:
                if voice["ShortName"] == voice_name or voice["FriendlyName"] == voice_name:
                    voice_info = voice
                    break

            if not voice_info:
                return self._create_error_response(
                    "NotFoundError",
                    f"Voice '{voice_name}' not found",
                    request_id=request_id
                )

            execution_time = (time.time() - start_time) * 1000

            return self._create_success_response(
                result={
                    "operation": "get_voice_info",
                    "success": True,
                    "voice_info": {
                        "name": voice_info["ShortName"],
                        "display_name": voice_info["FriendlyName"], 
                        "locale": voice_info["Locale"],
                        "gender": voice_info["Gender"],
                        "content_categories": voice_info.get("VoiceTag", {}).get("ContentCategories", []),
                        "voice_personalities": voice_info.get("VoiceTag", {}).get("VoicePersonalities", []),
                        "status": voice_info.get("Status", ""),
                        "suggested_codec": voice_info.get("SuggestedCodec", "")
                    },
                    "execution_time_ms": execution_time
                },
                request_id=request_id
            )

        except Exception as e:
            return self._create_error_response(
                "TTSError",
                f"Failed to get voice info: {e}",
                request_id=request_id
            )

    def get_help(self) -> str:
        """Get comprehensive help text for Edge TTS tool."""
        return """Edge TTS Tool

DESCRIPTION:
    Real text-to-speech using Microsoft Edge Speech Services.
    High-quality voices with multilingual support and natural speech.

INSTALLATION:
    pip install edge-tts

OPERATIONS:
    list_voices       - List available voices with filtering
    synthesize        - Generate WAV from text
    get_voice_info    - Get detailed voice information

PARAMETERS:
    operation (string, required)
        list_voices | synthesize | get_voice_info

    voice (string, optional for list_voices, recommended for synthesize)
        Voice name, e.g.:
        - en-US-AriaNeural (English US, Female)
        - en-GB-RyanNeural (English UK, Male) 
        - pl-PL-MarekNeural (Polish, Male)
        - fr-FR-DeniseNeural (French, Female)
        - de-DE-KatjaNeural (German, Female)

    text (string, required for synthesize)
        Text to synthesize

    file_path (string, optional)
        Output WAV path. If omitted, generated automatically.

    language (string, optional)
        Filter voices by locale (e.g., 'en-US', 'pl-PL')

    gender (string, optional)
        Filter voices by gender: Male | Female

    max_results (int, optional)
        For list_voices, range 1-500. Default: 50

EXAMPLES:
    1. List English voices:
       {"operation": "list_voices", "language": "en-US", "max_results": 10}

    2. Basic synthesis:
       {
         "operation": "synthesize",
         "text": "Hello, this is a test of Edge TTS!",
         "voice": "en-US-AriaNeural",
         "file_path": "outputs/hello.wav"
       }

    3. Multilingual synthesis:
       {
         "operation": "synthesize", 
         "text": "Witaj świecie! To jest test TTS.",
         "voice": "pl-PL-MarekNeural"
       }

    4. Voice information:
       {"operation": "get_voice_info", "voice": "en-US-AriaNeural"}

RESPONSE FORMAT:
    Success:
        {
            "status": "success",
            "result": {
                "operation": "synthesize",
                "success": true,
                "output_file": "outputs/hello.wav",
                "execution_time_ms": 1234.56
            }
        }

    Error:
        {
            "status": "error",
            "error": {
                "message": "Synthesis failed: ...",
                "type": "TTSError"
            }
        }

NOTES:
    - Edge TTS provides 300+ voices in 100+ languages
    - No API key required - uses Microsoft Edge Speech Services
    - Output format is WAV with high quality audio
    - Network connection required for synthesis
    - Voice names are case-sensitive"""