NAME := connector_metro
include ../glue/Makefile.common
all: build
lint: lint_pylint
tests: tests_nose
