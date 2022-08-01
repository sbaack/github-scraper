.PHONY: update-deps help

# Calling make without arguments updates pip-tools and pinned requirements
all: update-deps

help:
	@echo 'update-deps: install or update pip-tools and update pinned requirements'

update-deps:
	python -m pip install --upgrade pip
	python -m pip install -Ur requirements.in
