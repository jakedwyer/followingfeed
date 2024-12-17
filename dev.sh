#!/bin/bash

# Development environment management script

# Function to display help message
show_help() {
    echo "Development Environment Management Script"
    echo "Usage: ./dev.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start     - Start the development environment"
    echo "  stop      - Stop the development environment"
    echo "  restart   - Restart the development environment"
    echo "  logs      - Show logs from the development environment"
    echo "  build     - Rebuild the development environment"
    echo "  test      - Run tests"
    echo "  clean     - Clean up development environment (remove containers, volumes)"
    echo "  help      - Show this help message"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker is not running"
        exit 1
    fi
}

# Start development environment
start_dev() {
    check_docker
    echo "Starting development environment..."
    docker compose -f docker-compose.dev.yml up -d
    echo "Development environment started"
}

# Stop development environment
stop_dev() {
    check_docker
    echo "Stopping development environment..."
    docker compose -f docker-compose.dev.yml down
    echo "Development environment stopped"
}

# Restart development environment
restart_dev() {
    stop_dev
    start_dev
}

# Show logs
show_logs() {
    check_docker
    docker compose -f docker-compose.dev.yml logs -f
}

# Build development environment
build_dev() {
    check_docker
    echo "Building development environment..."
    docker compose -f docker-compose.dev.yml build
    echo "Build complete"
}

# Run tests
run_tests() {
    check_docker
    echo "Running tests..."
    docker compose -f docker-compose.dev.yml run --rm followfeed python -m pytest tests/
}

# Clean up development environment
clean_dev() {
    check_docker
    echo "Cleaning up development environment..."
    docker compose -f docker-compose.dev.yml down -v
    echo "Cleanup complete"
}

# Main script logic
case "$1" in
    "start")
        start_dev
        ;;
    "stop")
        stop_dev
        ;;
    "restart")
        restart_dev
        ;;
    "logs")
        show_logs
        ;;
    "build")
        build_dev
        ;;
    "test")
        run_tests
        ;;
    "clean")
        clean_dev
        ;;
    "help"|"")
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac 