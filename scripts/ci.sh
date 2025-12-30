#!/bin/bash
#
# CI Script for Dolmenwood Virtual DM
# Runs tests, type checking, and formatting checks
#
# Usage:
#   ./scripts/ci.sh          # Run all checks
#   ./scripts/ci.sh --fix    # Run checks and auto-fix formatting issues
#   ./scripts/ci.sh tests    # Run only tests
#   ./scripts/ci.sh mypy     # Run only type checking
#   ./scripts/ci.sh black    # Run only formatting check

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track overall success
OVERALL_SUCCESS=true

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if a command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 is not installed. Please install it with: pip install $1"
        exit 1
    fi
}

# Run pytest
run_tests() {
    print_header "Running Tests (pytest)"

    if python -m pytest tests/ -v --tb=short; then
        print_success "All tests passed"
        return 0
    else
        print_error "Tests failed"
        OVERALL_SUCCESS=false
        return 1
    fi
}

# Run mypy type checking
run_mypy() {
    print_header "Running Type Checking (mypy)"

    if python -m mypy src/; then
        print_success "Type checking passed"
        return 0
    else
        print_error "Type checking failed"
        OVERALL_SUCCESS=false
        return 1
    fi
}

# Run black formatting check
run_black() {
    local fix_mode=$1
    print_header "Running Formatting Check (black)"

    if [ "$fix_mode" = "fix" ]; then
        echo "Running black in fix mode..."
        if python -m black src/ tests/; then
            print_success "Formatting fixed"
            return 0
        else
            print_error "Formatting fix failed"
            OVERALL_SUCCESS=false
            return 1
        fi
    else
        echo "Running black in check mode..."
        if python -m black --check src/ tests/; then
            print_success "Formatting check passed"
            return 0
        else
            print_warning "Formatting issues found. Run with --fix to auto-fix."
            OVERALL_SUCCESS=false
            return 1
        fi
    fi
}

# Print summary
print_summary() {
    print_header "Summary"

    if [ "$OVERALL_SUCCESS" = true ]; then
        print_success "All checks passed!"
        exit 0
    else
        print_error "Some checks failed. See above for details."
        exit 1
    fi
}

# Main execution
main() {
    # Change to repository root
    cd "$(dirname "$0")/.."

    # Parse arguments
    FIX_MODE=""
    RUN_TESTS=true
    RUN_MYPY=true
    RUN_BLACK=true

    while [[ $# -gt 0 ]]; do
        case $1 in
            --fix)
                FIX_MODE="fix"
                shift
                ;;
            tests)
                RUN_TESTS=true
                RUN_MYPY=false
                RUN_BLACK=false
                shift
                ;;
            mypy)
                RUN_TESTS=false
                RUN_MYPY=true
                RUN_BLACK=false
                shift
                ;;
            black)
                RUN_TESTS=false
                RUN_MYPY=false
                RUN_BLACK=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [options] [command]"
                echo ""
                echo "Commands:"
                echo "  tests    Run only pytest tests"
                echo "  mypy     Run only mypy type checking"
                echo "  black    Run only black formatting check"
                echo ""
                echo "Options:"
                echo "  --fix    Auto-fix formatting issues with black"
                echo "  --help   Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0              # Run all checks"
                echo "  $0 --fix        # Run all checks and fix formatting"
                echo "  $0 tests        # Run only tests"
                echo "  $0 black --fix  # Fix formatting only"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║             Dolmenwood Virtual DM - CI Checks                             ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Check dependencies
    check_command python

    # Run selected checks
    if [ "$RUN_TESTS" = true ]; then
        run_tests || true
    fi

    if [ "$RUN_MYPY" = true ]; then
        run_mypy || true
    fi

    if [ "$RUN_BLACK" = true ]; then
        run_black "$FIX_MODE" || true
    fi

    # Print summary
    print_summary
}

# Run main function
main "$@"
