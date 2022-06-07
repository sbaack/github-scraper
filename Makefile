.PHONY: update-deps help

# Calling make without arguments updates pip-tools and pinned requirements
all: update-deps

help:
	@echo 'update-deps: install or update pip-tools and update pinned requirements'

update-deps:
	pip install --upgrade pip setuptools pip-tools
	pip-compile --quiet --allow-unsafe
	pip-sync
