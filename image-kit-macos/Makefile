PYTHON ?= /opt/homebrew/bin/python3.11
VENV := .venv
BIN := $(VENV)/bin

.PHONY: all setup run bundle clean

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
	$(BIN)/pyinstaller --noconfirm --windowed --name "ImageKit" \
		--hidden-import "pynput.keyboard._darwin" \
		--hidden-import "pynput.mouse._darwin" \
		--paths . \
		src/main.py
	@printf "[Paths]\nPrefix = ../Frameworks/PyQt6/Qt6\nPlugins = plugins\n" > dist/ImageKit.app/Contents/Resources/qt.conf
	@cp dist/ImageKit.app/Contents/Resources/qt.conf dist/ImageKit.app/Contents/MacOS/qt.conf
	@$(PYTHON) -c "import plistlib; p='dist/ImageKit.app/Contents/Info.plist'; d=plistlib.load(open(p,'rb')); d['CFBundleIdentifier']='com.imagekit.app'; d['NSAccessibilityUsageDescription']='ImageKit requires accessibility permission to listen for global hotkeys across applications.'; d['NSAppleEventsUsageDescription']='ImageKit requires apple events permission to interact with applications.'; d['NSScreenCaptureUsageDescription']='ImageKit requires screen recording permission to capture the screen for OCR.'; plistlib.dump(d, open(p,'wb'))"
	@codesign --force --deep --sign - dist/ImageKit.app
	@echo "\n✨ Build complete! You can find ImageKit.app in the dist/ folder:"
	@echo "   open dist/ImageKit.app"

clean:
	rm -rf $(VENV) build dist *.egg-info __pycache__ src/__pycache__ src/*/__pycache__ *.spec
