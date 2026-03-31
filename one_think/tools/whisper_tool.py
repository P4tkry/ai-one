from one_think.tools import Tool
import os
import json
from pathlib import Path
from typing import Tuple, Optional
from dotenv import load_dotenv

load_dotenv()


class WhisperTool(Tool):
    """Tool for audio transcription using OpenAI Whisper."""
    name = "whisper"
    description = "Transcribe audio files (local or URL) using OpenAI Whisper"
    
    def __init__(self):
        super().__init__()
        self.models = ["base", "small", "medium", "large"]
        self.default_model = "base"
        self.output_formats = ["json", "text", "srt", "vtt"]
    
    def execute(self, arguments: dict[str, str]) -> Tuple[str, str]:
        """Execute the tool operation."""
        # Check for help first
        if arguments.get("help"):
            return self._show_help()
        
        operation = arguments.get("operation")
        
        if not operation:
            return "", "Missing required argument: 'operation'"
        
        # Execute operations
        if operation == "transcribe":
            audio_path = arguments.get("audio_path")
            language = arguments.get("language", "")
            model = arguments.get("model", self.default_model)
            format_type = arguments.get("format", "json")
            temperature = arguments.get("temperature", "0")
            return self._transcribe(audio_path, language, model, format_type, temperature)
        
        elif operation == "list_models":
            return self._list_models()
        
        elif operation == "help":
            return self._show_help()
        
        else:
            return "", (
                f"Unknown operation: '{operation}'. "
                "Valid operations: transcribe, list_models, help"
            )
    
    def _transcribe(
        self,
        audio_path: str,
        language: str = "",
        model: str = "base",
        format_type: str = "json",
        temperature: str = "0"
    ) -> Tuple[str, str]:
        """Transcribe audio file or URL."""
        if not audio_path:
            return "", "Missing required argument: audio_path"
        
        # Validate model
        if model not in self.models:
            return "", f"Invalid model: {model}. Available: {', '.join(self.models)}"
        
        # Validate format
        if format_type not in self.output_formats:
            return "", f"Invalid format: {format_type}. Available: {', '.join(self.output_formats)}"
        
        # Check if audio_path is URL or local file
        if audio_path.startswith(("http://", "https://")):
            return self._transcribe_url(audio_path, language, model, format_type, temperature)
        else:
            return self._transcribe_file(audio_path, language, model, format_type, temperature)
    
    def _transcribe_file(
        self,
        file_path: str,
        language: str,
        model: str,
        format_type: str,
        temperature: str
    ) -> Tuple[str, str]:
        """Transcribe local audio file using OpenAI Whisper Python package."""
        # Check if file exists
        if not os.path.exists(file_path):
            return "", f"Audio file not found: {file_path}"
        
        # Check file extension
        audio_extensions = ('.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm', '.mp4')
        if not file_path.lower().endswith(audio_extensions):
            return "", f"Unsupported audio format. Supported: {', '.join(audio_extensions)}"
        
        try:
            import whisper
            
            # Load model
            loaded_model = whisper.load_model(model)
            
            # Build transcribe kwargs
            transcribe_kwargs = {
                "language": language if language else None,
                "temperature": float(temperature) if temperature else 0.0,
            }
            
            # Remove None values (except temperature which can be 0)
            transcribe_kwargs = {k: v for k, v in transcribe_kwargs.items() if v is not None or k == "temperature"}
            
            # Transcribe
            result = loaded_model.transcribe(file_path, **transcribe_kwargs)
            
            # Format output
            return self._format_whisper_result(result, format_type, file_path)
            
        except ImportError:
            return "", (
                "OpenAI Whisper not installed. Install with:\n"
                "  pip install openai-whisper"
            )
        except Exception as e:
            return "", f"Error transcribing file: {type(e).__name__}: {e}"
    
    def _transcribe_url(
        self,
        url: str,
        language: str,
        model: str,
        format_type: str,
        temperature: str
    ) -> Tuple[str, str]:
        """Transcribe audio from URL."""
        try:
            import requests
            
            # Download audio temporarily
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            # Save to temporary file
            temp_file = f"/tmp/whisper_temp_{os.getpid()}.mp3"
            os.makedirs(os.path.dirname(temp_file) or ".", exist_ok=True)
            
            with open(temp_file, "wb") as f:
                f.write(response.content)
            
            try:
                # Transcribe temporary file
                result, error = self._transcribe_file(
                    temp_file, language, model, format_type, temperature
                )
                
                return result, error
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except ImportError:
            return "", "requests library not installed. Install with: pip install requests"
        except Exception as e:
            return "", f"Error downloading audio: {e}"
    
    def _parse_whisper_output(self, file_path: str, format_type: str, output: str) -> Tuple[str, str]:
        """Parse whisper output based on format."""
        try:
            # Whisper outputs files with specific extensions
            base_name = os.path.splitext(file_path)[0]
            output_file = f"{base_name}.{format_type}"
            
            if os.path.exists(output_file):
                with open(output_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Clean up output file
                try:
                    os.unlink(output_file)
                except:
                    pass
                
                if format_type == "json":
                    # Parse JSON and return nicely formatted
                    data = json.loads(content)
                    return json.dumps(data, indent=2, ensure_ascii=False), ""
                else:
                    # Return raw content for text, srt, vtt formats
                    result = {
                        "format": format_type,
                        "transcription": content,
                        "file": file_path
                    }
                    return json.dumps(result, indent=2, ensure_ascii=False), ""
            else:
                return "", f"Output file not found: {output_file}"
                
        except json.JSONDecodeError as e:
            return "", f"Error parsing output: {e}"
        except Exception as e:
            return "", f"Error processing output: {e}"
    
    def _format_whisper_result(self, result: dict, format_type: str, file_path: str) -> Tuple[str, str]:
        """Format Whisper result based on requested format."""
        try:
            if format_type == "json":
                # Return raw Whisper result as JSON (contains segments with timestamps)
                return json.dumps(result, indent=2, ensure_ascii=False), ""
            
            elif format_type == "text":
                # Extract plain text from result
                text = result.get("text", "")
                formatted = {
                    "format": "text",
                    "transcription": text,
                    "language": result.get("language", "unknown"),
                    "file": file_path
                }
                return json.dumps(formatted, indent=2, ensure_ascii=False), ""
            
            elif format_type == "srt":
                # Convert to SRT format (SubRip subtitles)
                srt_content = self._segments_to_srt(result.get("segments", []))
                formatted = {
                    "format": "srt",
                    "transcription": srt_content,
                    "file": file_path
                }
                return json.dumps(formatted, indent=2, ensure_ascii=False), ""
            
            elif format_type == "vtt":
                # Convert to VTT format (WebVTT subtitles)
                vtt_content = self._segments_to_vtt(result.get("segments", []))
                formatted = {
                    "format": "vtt",
                    "transcription": vtt_content,
                    "file": file_path
                }
                return json.dumps(formatted, indent=2, ensure_ascii=False), ""
            
            else:
                return "", f"Unknown format: {format_type}"
                
        except Exception as e:
            return "", f"Error formatting result: {e}"
    
    def _segments_to_srt(self, segments: list) -> str:
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
    
    def _segments_to_vtt(self, segments: list) -> str:
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
        """Convert seconds to time format (HH:MM:SS,mmm for SRT or HH:MM:SS.mmm for VTT)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        separator = "," if srt else "."
        return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"
    
    def _list_models(self) -> Tuple[str, str]:
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
            "audio_formats": [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm", ".mp4"]
        }
        
        return json.dumps(models_info, indent=2), ""
    
    def _show_help(self) -> Tuple[str, str]:
        """Show help information."""
        help_text = """Whisper Audio Transcription Tool

DESCRIPTION:
    Transcribe audio files (local or URL) using OpenAI Whisper.
    Converts speech to text with support for 100+ languages.

OPERATIONS:
    
    transcribe      - Transcribe audio file or URL
    list_models     - Show available models and details
    help            - Show this help message

PREREQUISITES:

    Install Whisper:
    pip install openai-whisper

    Optional (for URL support):
    pip install requests

TRANSCRIBE OPERATION:

    Transcribe local audio file:
    {"operation": "transcribe", "audio_path": "/path/to/audio.mp3"}
    
    Transcribe from URL:
    {"operation": "transcribe", 
     "audio_path": "https://example.com/audio.mp3"}
    
    Specify language (faster and more accurate):
    {"operation": "transcribe",
     "audio_path": "audio.mp3",
     "language": "en"}
    
    Use different model (larger = more accurate but slower):
    {"operation": "transcribe",
     "audio_path": "audio.mp3",
     "model": "large"}
    
    Different output format:
    {"operation": "transcribe",
     "audio_path": "audio.mp3",
     "format": "srt"}
    
    With all options:
    {"operation": "transcribe",
     "audio_path": "audio.mp3",
     "language": "en",
     "model": "small",
     "format": "json",
     "temperature": "0.3"}

PARAMETERS:

    audio_path (required, string)
        Path to audio file (local) or URL.
        Supported: .mp3, .wav, .m4a, .flac, .ogg, .webm, .mp4
    
    language (optional, string)
        Language code (e.g., 'en', 'pl', 'es', 'fr', 'de').
        Leave empty for auto-detection.
        Common: en, es, fr, de, it, pl, ru, zh, ja, ko
    
    model (optional, string)
        Model size: base, small, medium, large
        Default: base (fastest)
        Larger models are more accurate but slower
    
    format (optional, string)
        Output format: json, text, srt, vtt
        Default: json (structured output)
        - json: Structured with segments and timestamps
        - text: Plain text transcription
        - srt: SubRip format (video subtitles)
        - vtt: WebVTT format (web subtitles)
    
    temperature (optional, string)
        Sampling temperature (0-1, default 0)
        Higher = more creative/varied, Lower = more consistent
    
EXAMPLES:

    1. Quick transcription (English):
    {"operation": "transcribe", "audio_path": "recording.mp3"}
    
    2. High-quality transcription (Polish):
    {"operation": "transcribe",
     "audio_path": "podcast.wav",
     "language": "pl",
     "model": "large"}
    
    3. Get subtitles in SRT format:
    {"operation": "transcribe",
     "audio_path": "video.mp4",
     "format": "srt"}
    
    4. Transcribe from YouTube (download first):
    {"operation": "transcribe",
     "audio_path": "https://example.com/audio.m4a",
     "language": "en"}
      ],
      "language": "en"
    }
    
    Text: Plain transcribed text
    
    SRT: Subtitle format with timestamps
    1
    00:00:00,000 --> 00:00:03,000
    First sentence
    
    VTT: WebVTT subtitle format

MODELS:

    base (140M)     - Fast, good for quick transcription
    small (244M)    - Balanced speed and accuracy
    medium (769M)   - Better accuracy
    large (2.9G)    - Best accuracy (slowest)

SUPPORTED LANGUAGES:
    Afrikaans, Arabic, Armenian, Assamese, Azerbaijani, Bashkir,
    Basque, Belarusian, Bengali, Bosnian, Bulgarian, Catalan,
    Cebuano, Czech, Chinese, Danish, Dutch, English, Estonian,
    Finnish, French, Galician, German, Gujarati, Hebrew, Hindi,
    Hungarian, Icelandic, Indonesian, Italian, Japanese, Javanese,
    Kannada, Kazakh, Khmer, Korean, Lao, Latin, Latvian,
    Lithuanian, Luxembourgish, Macedonian, Malay, Malayalam,
    Marathi, Burmese, Nepali, Norwegian, Occitan, Pashto, Persian,
    Polish, Portuguese, Punjabi, Romanian, Russian, Sanskrit,
    Serbian, Slovak, Slovenian, Somali, Spanish, Sundanese,
    Swahili, Swedish, Tagalog, Tajik, Tamil, Tatar, Telugu, Thai,
    Tigrinya, Turkish, Turkmen, Ukrainian, Urdu, Uzbek,
    Vietnamese, Welsh, Yiddish, Yoruba, and more...

WORKFLOW EXAMPLES:

    1. Transcribe audio to text:
       - Transcribe with auto-detect language
       - Get JSON with full segments and timestamps
       - Extract text field
    
    2. Create video subtitles:
       - Transcribe with format: "srt"
       - Use output directly in video editor
       - Perfect for YouTube, Vimeo, etc.
    
    3. Process podcast:
       - Transcribe with model: "large"
       - Get JSON format
       - Process segments with timestamps
    
    4. Real-time meeting notes:
       - Transcribe with language: "en"
       - Get precise timing for search

TROUBLESHOOTING:

    Error: "whisper: command not found"
    → Install Whisper: pip install openai-whisper
    
    Error: "Audio file not found"
    → Check file path and permissions
    
    Error: "Unsupported audio format"
    → Convert audio to mp3, wav, or m4a
    → Use ffmpeg: ffmpeg -i input.format -q:a 0 output.mp3
    
    Slow transcription:
    → Use smaller model (base) for faster results
    → Or use larger model (large) for better quality
    
    URL download fails:
    → Check URL is accessible
    → Install requests: pip install requests

PERFORMANCE:

    Model    | Speed      | Accuracy | Memory
    ---------|------------|----------|--------
    base     | Very Fast  | Good     | 1GB
    small    | Fast       | Better   | 1.5GB
    medium   | Moderate   | Very Good| 5GB
    large    | Slow       | Excellent| 10GB

NOTES:
    - First run downloads model (can take time)
    - Longer audio = longer processing
    - Language specification makes it faster
    - Works offline after model is downloaded
    - Supports streaming for live transcription
    - Output files are created in same directory as audio

API COMPARISON:
    Whisper (local): Free, offline, private, slower
    OpenAI API: Fast, cloud, paid, requires API key
    Google Speech-to-Text: Cloud, paid, different API
    
    This tool uses offline Whisper for privacy!
"""
        return help_text, ""
