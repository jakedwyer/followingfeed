# Development Guide

## Environment Setup

1. **Prerequisites**
   - Docker Desktop
   - Git
   - Python 3.12 (for local development outside Docker)

2. **Initial Setup**
   ```bash
   # Clone the repository
   git clone <repository-url>
   cd followingfeed

   # Switch to development branch
   git checkout development

   # Copy and configure environment file
   cp .env.development .env.development.local
   # Edit .env.development.local with your development credentials
   ```

3. **Development Environment**
   The project includes a development management script (`dev.sh`) for easy environment control:
   ```bash
   # Make the script executable
   chmod +x dev.sh

   # Start development environment
   ./dev.sh start

   # View logs
   ./dev.sh logs

   # Stop environment
   ./dev.sh stop
   ```

## Development Workflow

1. **Making Changes**
   - Always work on the `development` branch or feature branches
   - Use `docker-compose.dev.yml` for development (handled by dev.sh)
   - Changes are automatically synced with the container

2. **Testing**
   ```bash
   # Run tests
   ./dev.sh test
   ```

3. **Deployment**
   - Push changes to development branch
   - Create pull request to main branch
   - Automated deployment occurs when PR is merged

## Environment Variables

Development environment variables are stored in `.env.development`. Required variables:
- `TWITTER_API_KEY`
- `TWITTER_API_SECRET`
- `TWITTER_BEARER_TOKEN`
- `AIRTABLE_BASE_ID`
- `AIRTABLE_TOKEN`
- And others as specified in `.env.development`

## Docker Development Environment

The development environment includes:
- Hot reload for code changes
- Development-specific environment variables
- Exposed port 5001 for debugging
- Volume mounts for local development
- 2GB memory limit

## Troubleshooting

1. **Container Issues**
   ```bash
   # Clean up environment
   ./dev.sh clean
   
   # Rebuild
   ./dev.sh build
   ```

2. **Port Conflicts**
   - Development server runs on port 5001
   - Modify in `docker-compose.dev.yml` if needed

3. **Memory Issues**
   - Container is limited to 2GB memory
   - Adjust in `docker-compose.dev.yml` if needed

## Production Deployment

Automated deployment is handled by GitHub Actions when:
- Changes are pushed to main branch
- Pull requests are merged into main

Required GitHub Secrets:
- `SSH_PRIVATE_KEY`
- `SERVER_IP`
- `SERVER_USER` 