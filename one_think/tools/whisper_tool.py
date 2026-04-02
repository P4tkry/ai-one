"""
Whisper Tool - Full JSON migration with Pydantic schemas.
Audio transcription using OpenAI Whisper with structured responses and validation.
"""
import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from one_think.tools.base import Tool, ToolResponse

load_dotenv()

try:
    # Lazy import - only import when needed to avoid torch warnings
    # import whisper  # moved to execute() method
    import requests
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


class WhisperTool(Tool):
    """Tool for audio transcription using OpenAI Whisper."""
    
    name = "whisper"
    description = "Audio transcription using OpenAI Whisper"
    version = "2.0.0"
    
    # Pydantic schemas
    class Input(BaseModel):
        """Input parameters for audio transcription."""
        operation: Literal["transcribe", "translate"] = Field(default="transcribe", description="Operation: transcribe or translate to English")
        audio_file: Optional[str] = Field(default=None, description="Path to audio file")
        audio_url: Optional[str] = Field(default=None, description="URL to audio file")
        model_size: Optional[Literal["tiny", "base", "small", "medium", "large"]] = Field(default="base", description="Whisper model size")
        language: Optional[str] = Field(default=None, description="Audio language (auto-detect if None)")
        
    class Output(BaseModel):
        """Output format for transcription."""
        operation: str = Field(description="Operation performed")
        text: str = Field(description="Transcribed/translated text")
        language: Optional[str] = Field(description="Detected language")
        model_size: str = Field(description="Whisper model used")
        confidence: Optional[float] = Field(description="Transcription confidence")
        duration: Optional[float] = Field(description="Audio duration in seconds")
    """Tool for audio transcription using OpenAI Whisper."""
    
    name = "whisper"
    description = "Transcribe audio files (local or URL) using OpenAI Whisper"
    
    def __init__(self):
        super().__init__()
        self.models = ["base", "small", "medium", "large"]
        self.default_model = "base"
        self.output_formats = ["json", "text", "srt", "vtt"]
        self.audio_extensions = ('.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm', '.mp4')
    
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute transcription with JSON response."""
        
        # Check for help request first
        if params.get("help"):
            return self._create_success_response(
                result={"help": self.get_help()},
                request_id=request_id
            )
        
        # Check if Whisper is available
        if not WHISPER_AVAILABLE:
            return self._create_error_response(
                "OpenAI Whisper not installed. Install with: pip install openai-whisper requests",
                request_id=request_id
            )
        
        # Validate operation
        operation = params.get("operation")
        if not operation:
            return self._create_error_response(
                "Missing required parameter: 'operation'",
                request_id=request_id
            )
        
        # Route to operation handlers
        if operation == "transcribe":
            return self._transcribe(params, request_id)
        elif operation == "list_models":
            return self._list_models(request_id)
        else:
            return self._create_error_response(
                f"Unknown operation: '{operation}'. Valid operations: transcribe, list_models",
                request_id=request_id
            )
    
    def _transcribe(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Transcribe audio file or URL."""
        audio_path = params.get("audio_path")
        if not audio_path:
            return self._create_error_response(
                "Missing required parameter: 'audio_path'",
                request_id=request_id
            )
        
        # Validate and get parameters
        language = params.get("language", "")
        model = params.get("model", self.default_model)
        format_type = params.get("format", "json")
        temperature = params.get("temperature", "0")
        
        # Validate model
        if model not in self.models:
            return self._create_error_response(
                f"Invalid model: {model}. Available: {', '.join(self.models)}",
                request_id=request_id
            )
        
        # Validate format
        if format_type not in self.output_formats:
            return self._create_error_response(
                f"Invalid format: {format_type}. Available: {', '.join(self.output_formats)}",
                request_id=request_id
            )
        
        # Check if audio_path is URL or local file
        if audio_path.startswith(("http://", "https://")):
            return self._transcribe_url(audio_path, language, model, format_type, temperature, request_id)
        else:
            return self._transcribe_file(audio_path, language, model, format_type, temperature, request_id)
    
    def _transcribe_file(
        self,
        file_path: str,
        language: str,
        model: str,
        format_type: str,
        temperature: str,
        request_id: Optional[str]
    ) -> ToolResponse:
        """Transcribe local audio file."""
        
        # Lazy import whisper to avoid torch warnings during module loading
        try:
            import whisper
        except ImportError:
            return self._create_error_response(
                "Whisper library not available. Please install: pip install openai-whisper",
                request_id=request_id
            )
        
        # Check if file exists
        if not os.path.exists(file_path):
            return self._create_error_response(
                f"Audio file not found: {file_path}",
                request_id=request_id
            )
        
        # Check file extension
        if not file_path.lower().endswith(self.audio_extensions):
            return self._create_error_response(
                f"Unsupported audio format. Supported: {', '.join(self.audio_extensions)}",
                request_id=request_id
            )
        
        try:
            # Load model
            loaded_model = whisper.load_model(model)
            
            # Build transcribe kwargs
            transcribe_kwargs = {
                "language": language if language else None,
                "temperature": float(temperature) if temperature else 0.0,
            }
            
            # Remove None values
            transcribe_kwargs = {k: v for k, v in transcribe_kwargs.items() if v is not None or k == "temperature"}
            
            # Transcribe
            result = loaded_model.transcribe(file_path, **transcribe_kwargs)
            
            # Format output
            return self._format_whisper_result(result, format_type, file_path, request_id)
            
        except Exception as e:
            return self._create_error_response(
                f"Error transcribing file: {type(e).__name__}: {e}",
                request_id=request_id
            )
    
    def _transcribe_url(
        self,
        url: str,
        language: str,
        model: str,
        format_type: str,
        temperature: str,
        request_id: Optional[str]
    ) -> ToolResponse:
        """Transcribe audio from URL."""
        
        # Lazy import whisper to avoid torch warnings during module loading
        try:
            import whisper
        except ImportError:
            return self._create_error_response(
                "Whisper library not available. Please install: pip install openai-whisper",
                request_id=request_id
            )
            
        try:
            # Download audio temporarily
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_file.write(response.content)
                temp_path = tmp_file.name
            
            try:
                # Transcribe temporary file
                return self._transcribe_file(temp_path, language, model, format_type, temperature, request_id)
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            return self._create_error_response(
                f"Error downloading audio: {e}",
                request_id=request_id
            )
    
    def _format_whisper_result(
        self, 
        result: dict, 
        format_type: str, 
        file_path: str, 
        request_id: Optional[str]
    ) -> ToolResponse:
        """Format Whisper result based on requested format."""
        try:
            if format_type == "json":
                # Return structured Whisper result
                formatted_result = {
                    "file_path": file_path,
                    "text": result.get("text", ""),
                    "language": result.get("language", "unknown"),
                    "segments": result.get("segments", []),
                    "format": "json"
                }
                
            elif format_type == "text":
                # Extract plain text
                formatted_result = {
                    "file_path": file_path,
                    "text": result.get("text", ""),
                    "language": result.get("language", "unknown"),
                    "format": "text"
                }
                
            elif format_type == "srt":
                # Convert to SRT format
                srt_content = self._segments_to_srt(result.get("segments", []))
                formatted_result = {
                    "file_path": file_path,
                    "srt_content": srt_content,
                    "language": result.get("language", "unknown"),
                    "format": "srt"
                }
                
            elif format_type == "vtt":
                # Convert to VTT format
                vtt_content = self._segments_to_vtt(result.get("segments", []))
                formatted_result = {
                    "file_path": file_path,
                    "vtt_content": vtt_content,
                    "language": result.get("language", "unknown"),
                    "format": "vtt"
                }
                
            else:
                return self._create_error_response(
                    f"Unknown format: {format_type}",
                    request_id=request_id
                )
            
            return self._create_success_response(
                result=formatted_result,
                request_id=request_id
            )
                
        except Exception as e:
            return self._create_error_response(
                f"Error formatting result: {e}",
                request_id=request_id
            )
    
    def _segments_to_srt(self, segments: List[Dict]) -> str:
        """Convert Whisper segments to SRT subtitle format."""
        srt_lines = []
        for idx, segment in enumerate(segments, 1):
            start = self._seconds_to_time(segment.get("start", 0), srt=True)
            end = self._seconds_to_time(segment.get("end", 0), srt=True)
            text = segment.get("text", "").strip()
            
            if text:
                srt_lines.append(f"{idx}")
                srt_lines.append(f"{start} --> {end}")
                srt_lines.append(text)
                srt_lines.append("")
        
        return "\n".join(srt_lines)
    
    def _segments_to_vtt(self, segments: List[Dict]) -> str:
        """Convert Whisper segments to VTT subtitle format."""
        vtt_lines = ["WEBVTT\n"]
        
        for segment in segments:
            start = self._seconds_to_time(segment.get("start", 0), srt=False)
            end = self._seconds_to_time(segment.get("end", 0), srt=False)
            text = segment.get("text", "").strip()
            
            if text:
                vtt_lines.append(f"{start} --> {end}")
                vtt_lines.append(text)
                vtt_lines.append("")
        
        return "\n".join(vtt_lines)
    
    @staticmethod
    def _seconds_to_time(seconds: float, srt: bool = True) -> str:
        """Convert seconds to time format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        separator = "," if srt else "."
        return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"
    
    def _list_models(self, request_id: Optional[str]) -> ToolResponse:
        """List available Whisper models."""
        models_info = {
            "available_models": self.models,
            "default_model": self.default_model,
            "model_details": {
                "base": {
                    "size": "140M",
                    "description": "Small model, fast but less accurate",
                    "recommended_for": "quick transcription"
                },
                "small": {
                    "size": "244M",
                    "description": "Balanced model",
                    "recommended_for": "general use"
                },
                "medium": {
                    "size": "769M",
                    "description": "Large model, slower but more accurate",
                    "recommended_for": "high-quality transcription"
                },
                "large": {
                    "size": "2.9G",
                    "description": "Largest model, slowest but most accurate",
                    "recommended_for": "production use"
                }
            },
            "supported_languages": "100+ languages (auto-detected or specify)",
            "audio_formats": list(self.audio_extensions),
            "output_formats": self.output_formats
        }
        
        return self._create_success_response(
            result=models_info,
            request_id=request_id
        )
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return """Whisper Audio Transcription Tool

DESCRIPTION:
    Transcribe audio files (local or URL) using OpenAI Whisper.
    Converts speech to text with support for 100+ languages.

OPERATIONS:
    transcribe    - Transcribe audio file or URL
    list_models   - Show available models and details

PARAMETERS:
    operation (string, required)
        Operation to perform: transcribe, list_models

    For transcribe operation:
        audio_path (string, required)
            Path to audio file (local) or URL

        language (string, optional)
            Language code (e.g., 'en', 'pl', 'es'). Auto-detect if not specified.

        model (string, optional)
            Model size: base, small, medium, large. Default: base

        format (string, optional)
            Output format: json, text, srt, vtt. Default: json

        temperature (string, optional)
            Sampling temperature (0-1). Default: 0

EXAMPLES:
    1. Basic transcription:
       {"operation": "transcribe", "audio_path": "recording.mp3"}

    2. High-quality Polish transcription:
       {"operation": "transcribe", "audio_path": "podcast.wav", "language": "pl", "model": "large"}

    3. Generate subtitles:
       {"operation": "transcribe", "audio_path": "video.mp4", "format": "srt"}

    4. Transcribe from URL:
       {"operation": "transcribe", "audio_path": "https://example.com/audio.mp3"}

    5. List available models:
       {"operation": "list_models"}

PREREQUISITES:
    Install dependencies:
        pip install openai-whisper requests

SUPPORTED FORMATS:
    Audio: .mp3, .wav, .m4a, .flac, .ogg, .webm, .mp4
    Output: json (structured), text (plain), srt (subtitles), vtt (web subtitles)

RESPONSE FORMAT:
    Success (transcribe):
        {
            "status": "success",
            "result": {
                "file_path": "recording.mp3",
                "text": "Transcribed text here...",
                "language": "en",
                "segments": [...],  // for json format
                "format": "json"
            }
        }
    
    Error:
        {
            "status": "error",
            "error": {
                "message": "Error description",
                "type": "ToolExecutionError"
            }
        }

MODELS:
    base (140M)     - Fast, good for quick transcription
    small (244M)    - Balanced speed and accuracy
    medium (769M)   - Better accuracy
    large (2.9G)    - Best accuracy (slowest)

NOTES:
    - First run downloads model (can take time)
    - Language specification makes transcription faster
    - Works offline after model download
    - URL support requires internet connection
    - All responses in structured JSON format
"""