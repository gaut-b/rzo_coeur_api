.PHONY: messages compilemessages

# Extract translatable strings, ignoring both virtualenv directories.
# --no-obsolete drops #~ entries for strings no longer in the codebase.
messages:
	uv run python manage.py makemessages --locale fr --ignore=venv --ignore=.venv --no-obsolete

# Compile .po → .mo binaries.
compilemessages:
	uv run python manage.py compilemessages --locale fr
