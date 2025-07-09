#!/bin/bash

# RefNet Docker開発環境管理スクリプト

set -e

COMPOSE_FILE="docker-compose.yml"
OVERRIDE_FILE="docker-compose.override.yml"

case "$1" in
    "up")
        echo "🚀 Starting RefNet development environment..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE up -d
        echo "✅ Environment started. Access:"
        echo "   API: http://localhost/api/"
        echo "   Flower: http://localhost/flower/"
        echo "   Adminer: http://localhost:8080/"
        echo "   Output: http://localhost/output/"
        ;;

    "down")
        echo "🛑 Stopping RefNet environment..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE down
        ;;

    "reset")
        echo "🔄 Resetting RefNet environment..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE down -v
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE up -d
        ;;

    "logs")
        service=${2:-}
        if [ -n "$service" ]; then
            docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE logs -f "$service"
        else
            docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE logs -f
        fi
        ;;

    "exec")
        service=${2:-api}
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE exec "$service" bash
        ;;

    "migrate")
        echo "🔧 Running database migrations..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE exec api refnet-shared migrate upgrade
        ;;

    "test")
        echo "🧪 Running tests..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE exec api moon run shared:check
        ;;

    "status")
        echo "📊 RefNet services status:"
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE ps
        ;;

    *)
        echo "RefNet Docker Management Script"
        echo ""
        echo "Usage: $0 {up|down|reset|logs|exec|migrate|test|status}"
        echo ""
        echo "Commands:"
        echo "  up      - Start all services"
        echo "  down    - Stop all services"
        echo "  reset   - Reset environment (remove volumes)"
        echo "  logs    - Show logs (optionally for specific service)"
        echo "  exec    - Execute bash in service container"
        echo "  migrate - Run database migrations"
        echo "  test    - Run tests"
        echo "  status  - Show service status"
        exit 1
        ;;
esac
