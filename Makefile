VERSION := $(shell uv run python -c 'from bt_web_report_manager import __version__; print(__version__)')
RELEASE_ZIP := dist/bt-web-report-manager-$(VERSION).zip
RELEASE_DMG := dist/bt-web-report-manager-$(VERSION).dmg
RELEASE_TITLE ?= v$(VERSION)
RELEASE_NOTES ?= release-notes.md
CODESIGN_IDENTITY ?= 2D9B3302F8D8203D837B071A3CFAF5CD9FEACF4E
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
	if [ -f "$(RELEASE_DMG)" ]; then \
		gh release upload "v$(VERSION)" "$(RELEASE_DMG)" --repo bldgtyp/bt-web-report-manager --clobber; \
	fi

test:
	uv run black --check src tests
	uv run mypy src tests
	uv run pytest
