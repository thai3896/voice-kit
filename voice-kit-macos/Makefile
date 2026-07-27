PYTHON ?= /opt/homebrew/bin/python3.11
VENV := .venv
BIN := $(VENV)/bin

.PHONY: all setup run bundle clean test

all: setup

setup:
	@if [ ! -f "$(PYTHON)" ]; then \
		echo "Using system python3 as fallback..."; \
		python3 -m venv $(VENV); \
	else \
		$(PYTHON) -m venv $(VENV); \
	fi
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e .

run:
	$(BIN)/python -m src.main

bundle: setup
	$(BIN)/pip install pyinstaller
	$(BIN)/pyinstaller --noconfirm --windowed --name "VoiceKit" \
		--collect-all sounddevice \
		--collect-all soundfile \
		--hidden-import "pynput.keyboard._darwin" \
		--hidden-import "pynput.mouse._darwin" \
		src/main.py
	@printf "[Paths]\nPrefix = ../Frameworks/PyQt6/Qt6\nPlugins = plugins\n" > dist/VoiceKit.app/Contents/Resources/qt.conf
	@cp dist/VoiceKit.app/Contents/Resources/qt.conf dist/VoiceKit.app/Contents/MacOS/qt.conf
	@$(PYTHON) -c "import plistlib; p='dist/VoiceKit.app/Contents/Info.plist'; d=plistlib.load(open(p,'rb')); d['CFBundleIdentifier']='com.voicekit.app'; d['NSMicrophoneUsageDescription']='VoiceKit requires microphone access to record and transcribe speech.'; d['NSAccessibilityUsageDescription']='VoiceKit requires accessibility permission to listen for global hotkeys across applications.'; d['NSAppleEventsUsageDescription']='VoiceKit requires apple events permission to interact with applications.'; plistlib.dump(d, open(p,'wb'))"
	@codesign --force --deep --sign - dist/VoiceKit.app
	@echo "\n✨ Build complete! You can find VoiceKit.app in the dist/ folder:"
	@echo "   open dist/VoiceKit.app"

clean:
	rm -rf $(VENV) build dist *.egg-info __pycache__ src/__pycache__ src/*/__pycache__ *.wav *.webm *.spec
