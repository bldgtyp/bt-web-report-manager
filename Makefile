VERSION := $(shell uv run python -c 'from bt_web_report_manager import __version__; print(__version__)')
RELEASE_ZIP := dist/bt-web-report-manager-$(VERSION).zip
RELEASE_TITLE ?= v$(VERSION)
RELEASE_NOTES ?= release-notes.md
CODESIGN_IDENTITY ?= Developer ID Application: Edwin May (JPJ3AJ5U8A)
NOTARIZE_PROFILE ?= bt-web-report-manager

.PHONY: build release-build publish-release test

build:
	./scripts/build-app.sh

release-build:
	CODESIGN_IDENTITY="$(CODESIGN_IDENTITY)" \
	NOTARIZE_PROFILE="$(NOTARIZE_PROFILE)" \
	./scripts/build-app.sh

publish-release:
	test -f "$(RELEASE_ZIP)"
	if gh release view "v$(VERSION)" --repo bldgtyp/bt-web-report-manager >/dev/null 2>&1; then \
		gh release upload "v$(VERSION)" "$(RELEASE_ZIP)" --repo bldgtyp/bt-web-report-manager --clobber; \
	else \
		if [ -f "$(RELEASE_NOTES)" ]; then \
			gh release create "v$(VERSION)" "$(RELEASE_ZIP)" --repo bldgtyp/bt-web-report-manager --title "$(RELEASE_TITLE)" --notes-file "$(RELEASE_NOTES)"; \
		else \
			gh release create "v$(VERSION)" "$(RELEASE_ZIP)" --repo bldgtyp/bt-web-report-manager --title "$(RELEASE_TITLE)" --generate-notes; \
		fi; \
	fi

test:
	uv run black --check src tests
	uv run mypy src tests
	uv run pytest
