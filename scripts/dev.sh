#!/bin/bash
set -e

COMMAND=${1:-help}

case $COMMAND in
    "install")
        echo "Installing all dependencies..."
        moon run :install
        ;;
    "check")
        echo "Running all checks..."
        moon run :check
        ;;
    "test")
        PROJECT=${2:-}
        if [ -z "$PROJECT" ]; then
            moon run :test
        else
            moon run $PROJECT:test
        fi
        ;;
    "lint")
        moon run :lint
        ;;
    "format")
        moon run :format
        ;;
    "clean")
        echo "Cleaning all projects..."
        moon run :clean
        ;;
    "help")
        echo "Usage: $0 {install|check|test|lint|format|clean|help}"
        echo ""
        echo "Commands:"
        echo "  install     Install all dependencies"
        echo "  check       Run all quality checks"
        echo "  test [proj] Run tests (all or specific project)"
        echo "  lint        Run linting"
        echo "  format      Format code"
        echo "  clean       Clean generated files"
        echo "  help        Show this help message"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
