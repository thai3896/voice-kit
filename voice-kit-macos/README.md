# VoiceKit macOS (Open Super Whisper Clone)

VoiceKit macOS is a desktop utility inspired by *Open Super Whisper* that lives in your macOS menu bar and provides instant voice-to-text transcription with auto-pasting anywhere on your system.

## Features
- **Global Hotkey & Floating HUD**: Press **Right Fn** (or Globe Key) from any app to open a sleek, frameless recording HUD overlay with real-time audio waveform animations.
- **Voice Editor API Integration**: Seamlessly connects to public or local Voice Editor servers (e.g. `wss://voice-editor.minipc.na/ws/transcribe`) for Whisper transcription and AI copy-editing (Ollama cleanup).
- **Pluggable Backends**: Easily switch between Voice Editor WebSocket API, OpenAI Whisper API, Groq Whisper API, or Local offline Whisper (`faster-whisper`).
- **Auto-Paste**: Automatically backs up your current clipboard, copies the transcribed & cleaned text, and simulates `Cmd + V` to insert text directly into your active input field.

## Prerequisites & Permissions
Because VoiceKit monitors global shortcuts, captures microphone audio, and simulates keyboard pasting, macOS requires permissions for your terminal or IDE:
1. Open **System Settings** -> **Privacy & Security** -> **Accessibility** and grant access to your Terminal / iTerm / VS Code.
2. Open **System Settings** -> **Privacy & Security** -> **Microphone** and grant access.

## Quick Start
1. Install dependencies and set up the virtual environment:
   ```bash
   make setup
   ```
2. Launch VoiceKit macOS:
   ```bash
   make run
   ```
3. Look for the circle icon in your macOS menu bar. Press **Right Fn** anywhere to start speaking!
