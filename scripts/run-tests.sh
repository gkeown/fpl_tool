#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

# Ensure venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install -e "$PROJECT_DIR[dev]"
fi

MODE="${1:-unit}"

case "$MODE" in
    unit)
        echo "Running unit tests..."
        "$VENV_DIR/bin/pytest" "$PROJECT_DIR/tests/" -v -m "not integration" "${@:2}"
        ;;
    integration)
        echo "Running integration tests (hits live APIs)..."
        "$VENV_DIR/bin/pytest" "$PROJECT_DIR/tests/test_integration/" -v -m integration "${@:2}"
        ;;
    all)
        echo "Running all tests..."
        "$VENV_DIR/bin/pytest" "$PROJECT_DIR/tests/" -v "${@:2}"
        ;;
    coverage)
        echo "Running unit tests with coverage..."
        "$VENV_DIR/bin/pytest" "$PROJECT_DIR/tests/" -v -m "not integration" \
            --cov="$PROJECT_DIR/src" --cov-report=term-missing "${@:2}"
        ;;
    *)
        echo "Usage: $0 {unit|integration|all|coverage}"
        echo ""
        echo "  unit         Run unit tests only (no network, default)"
        echo "  integration  Run integration tests (hits live APIs)"
        echo "  all          Run all tests"
        echo "  coverage     Run unit tests with coverage report"
        exit 1
        ;;
esac
