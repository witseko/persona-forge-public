.PHONY: setup settings ego report link unlink status clean languages profiles retake preserve public-export test lint audit

UV ?= uv
# Export the value as data so an answer filename cannot become shell syntax.
export ANSWERS
export DEST

setup:
	$(UV) run persona-forge setup

settings ego report link unlink status clean languages profiles retake preserve:
	$(UV) run persona-forge $@

# Build the limited public edition in a new folder: make public-export DEST=../persona-forge-public
public-export:
	@test -n "$$DEST" || { echo "Set DEST to a new folder outside this repository"; exit 1; }
	$(UV) run python -m persona_forge.public_export "$$DEST"

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

audit:
	$(UV) run pip-audit --local
