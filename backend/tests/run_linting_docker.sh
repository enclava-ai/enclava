#!/bin/bash
# Python linting and code quality checks (Docker version)

set -e

echo "🔍 Enclava Platform - Python Linting & Code Quality (Docker)"
echo "=========================================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
export LINTING_TARGET="${LINTING_TARGET:-app tests}"
export LINTING_STRICT="${LINTING_STRICT:-false}"

# We're already in the Docker container with packages installed

# Track linting results
failed_checks=()
passed_checks=()

# Function to run linting check
run_check() {
    local check_name=$1
    local command="$2"
    
    echo -e "\n${BLUE}🔍 Running $check_name...${NC}"
    
    if eval "$command"; then
        echo -e "${GREEN}✅ $check_name PASSED${NC}"
        passed_checks+=("$check_name")
        return 0
    else
        echo -e "${RED}❌ $check_name FAILED${NC}"
        failed_checks+=("$check_name")
        return 1
    fi
}

echo -e "\n${YELLOW}🔍 Code Quality Checks${NC}"
echo "======================"

# 1. Code formatting with Black
if run_check "Black Code Formatting" "black --check --diff $LINTING_TARGET"; then
    echo -e "${GREEN}✅ Code is properly formatted${NC}"
else
    echo -e "${YELLOW}⚠️ Code formatting issues found. Run 'black $LINTING_TARGET' to fix.${NC}"
fi

# 2. Import sorting with isort  
if run_check "Import Sorting (isort)" "isort --check-only --diff $LINTING_TARGET"; then
    echo -e "${GREEN}✅ Imports are properly sorted${NC}"
else
    echo -e "${YELLOW}⚠️ Import sorting issues found. Run 'isort $LINTING_TARGET' to fix.${NC}"
fi

# 3. Code linting with flake8
run_check "Code Linting (flake8)" "flake8 $LINTING_TARGET"

# 4. Type checking with mypy (lenient mode for now)
if run_check "Type Checking (mypy)" "mypy $LINTING_TARGET --ignore-missing-imports || true"; then
    echo -e "${YELLOW}ℹ️ Type checking completed (lenient mode)${NC}"
fi

# Generate summary report
echo -e "\n${YELLOW}📋 Linting Results Summary${NC}"
echo "=========================="

if [ ${#passed_checks[@]} -gt 0 ]; then
    echo -e "${GREEN}✅ Passed checks:${NC}"
    printf '   %s\n' "${passed_checks[@]}"
fi

if [ ${#failed_checks[@]} -gt 0 ]; then
    echo -e "${RED}❌ Failed checks:${NC}"
    printf '   %s\n' "${failed_checks[@]}"
fi

total_checks=$((${#passed_checks[@]} + ${#failed_checks[@]}))
if [ $total_checks -gt 0 ]; then
    success_rate=$(( ${#passed_checks[@]} * 100 / total_checks ))
    echo -e "\n${BLUE}📈 Code Quality Score: $success_rate% (${#passed_checks[@]}/$total_checks)${NC}"
else
    echo -e "\n${YELLOW}No checks were run${NC}"
fi

# Exit with appropriate code (non-blocking for now)
if [ ${#failed_checks[@]} -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All linting checks passed!${NC}"
    exit 0
else
    echo -e "\n${YELLOW}⚠️ Some linting issues found (non-blocking)${NC}"
    exit 0  # Don't fail CI/CD for linting issues for now
fi