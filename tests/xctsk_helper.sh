#!/bin/bash

# XCTSK Automation Helper Script
# Provides easy commands for common XCTSK operations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATION_SCRIPT="$SCRIPT_DIR/xctsk_automation.py"
XCTSK_DIR="$SCRIPT_DIR/xctsk"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if Python script exists
check_automation_script() {
    if [[ ! -f "$AUTOMATION_SCRIPT" ]]; then
        error "Automation script not found at $AUTOMATION_SCRIPT"
        exit 1
    fi
}

# Check if XCTSK directory exists
check_xctsk_dir() {
    if [[ ! -d "$XCTSK_DIR" ]]; then
        error "XCTSK directory not found at $XCTSK_DIR"
        exit 1
    fi
}

# Show usage information
show_usage() {
    echo "XCTSK Automation Helper"
    echo "======================"
    echo
    echo "Usage: $0 <command> [options]"
    echo
    echo "Commands:"
    echo "  upload [author]       Upload all XCTSK files (default author: 'Batch Upload')"
    echo "  download <codes>      Download tasks by comma-separated codes"
    echo "  qr <file>            Generate QR code for a single file"
    echo "  list                 List available XCTSK files"
    echo "  test                 Run automation tests"
    echo "  demo                 Run demonstration script"
    echo "  help                 Show this help message"
    echo
    echo "Examples:"
    echo "  $0 upload 'John Doe'"
    echo "  $0 download 12345,67890"
    echo "  $0 qr task_2025-01-19.xctsk"
    echo "  $0 list"
}

# Upload all XCTSK files
cmd_upload() {
    local author="${1:-Batch Upload}"
    
    check_automation_script
    check_xctsk_dir
    
    info "Uploading all XCTSK files with author: $author"
    
    python3 "$AUTOMATION_SCRIPT" upload \
        --directory "$XCTSK_DIR" \
        --author "$author" \
        --results-file "$SCRIPT_DIR/upload_results.json"
    
    if [[ $? -eq 0 ]]; then
        success "Upload completed"
        if [[ -f "$SCRIPT_DIR/upload_results.json" ]]; then
            info "Results saved to upload_results.json"
        fi
    else
        error "Upload failed"
        exit 1
    fi
}

# Download tasks by codes
cmd_download() {
    local codes="$1"
    
    if [[ -z "$codes" ]]; then
        error "Please provide task codes (comma-separated)"
        echo "Example: $0 download 12345,67890"
        exit 1
    fi
    
    check_automation_script
    
    local output_dir="$SCRIPT_DIR/downloaded_tasks"
    
    info "Downloading tasks: $codes"
    
    python3 "$AUTOMATION_SCRIPT" download \
        --codes "$codes" \
        --output "$output_dir"
    
    if [[ $? -eq 0 ]]; then
        success "Download completed"
        info "Files saved to: $output_dir"
    else
        error "Download failed"
        exit 1
    fi
}

# Generate QR code for a file
cmd_qr() {
    local file="$1"
    
    if [[ -z "$file" ]]; then
        error "Please provide an XCTSK file"
        echo "Example: $0 qr task_2025-01-19.xctsk"
        exit 1
    fi
    
    check_automation_script
    
    # Check if file exists (try both absolute and relative to xctsk dir)
    local input_file
    if [[ -f "$file" ]]; then
        input_file="$file"
    elif [[ -f "$XCTSK_DIR/$file" ]]; then
        input_file="$XCTSK_DIR/$file"
    else
        error "File not found: $file"
        exit 1
    fi
    
    local basename=$(basename "$input_file" .xctsk)
    local output_file="$SCRIPT_DIR/qr_${basename}.svg"
    
    info "Generating QR code for: $input_file"
    
    python3 "$AUTOMATION_SCRIPT" qr \
        --file "$input_file" \
        --output "$output_file"
    
    if [[ $? -eq 0 ]]; then
        success "QR code generated: $output_file"
    else
        error "QR code generation failed"
        exit 1
    fi
}

# List available XCTSK files
cmd_list() {
    check_xctsk_dir
    
    info "Available XCTSK files in $XCTSK_DIR:"
    echo
    
    local count=0
    for file in "$XCTSK_DIR"/*.xctsk; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            local size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo "?")
            printf "  %-30s (%s bytes)\n" "$basename" "$size"
            count=$((count + 1))
        fi
    done
    
    if [[ $count -eq 0 ]]; then
        warning "No XCTSK files found"
    else
        echo
        success "Found $count XCTSK files"
    fi
}

# Run tests
cmd_test() {
    check_automation_script
    
    info "Running automation tests..."
    
    local test_script="$SCRIPT_DIR/test_xctsk_automation.py"
    if [[ -f "$test_script" ]]; then
        cd "$SCRIPT_DIR"
        python3 "$test_script"
    else
        warning "Test script not found, running basic validation..."
        python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from xctsk_automation import XCTSKClient
print('✓ Import successful')
client = XCTSKClient()
print('✓ Client creation successful')
print('🎉 Basic validation passed')
"
    fi
}

# Run demonstration
cmd_demo() {
    check_automation_script
    
    local demo_script="$SCRIPT_DIR/xctsk_demo.py"
    if [[ -f "$demo_script" ]]; then
        info "Running demonstration script..."
        cd "$SCRIPT_DIR"
        python3 "$demo_script"
    else
        error "Demo script not found at $demo_script"
        exit 1
    fi
}

# Main command dispatcher
main() {
    local command="$1"
    shift
    
    case "$command" in
        upload)
            cmd_upload "$@"
            ;;
        download)
            cmd_download "$@"
            ;;
        qr)
            cmd_qr "$@"
            ;;
        list)
            cmd_list "$@"
            ;;
        test)
            cmd_test "$@"
            ;;
        demo)
            cmd_demo "$@"
            ;;
        help|--help|-h|"")
            show_usage
            ;;
        *)
            error "Unknown command: $command"
            echo
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
