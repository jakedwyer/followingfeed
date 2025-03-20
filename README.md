# FollowFeed

## Port Configuration

To avoid port conflicts when running multiple applications on the same machine, both the FollowFeed API and Nitter applications use configurable ports through environment variables.

### Default Ports
- FollowFeed API: 8000
- Nitter: 8081

### Changing Ports

You can change the ports by setting the following environment variables in your `.env` file:

```
API_PORT=8000  # Change to any available port
NITTER_PORT=8081  # Change to any available port
```

These environment variables are used in:
1. Docker Compose configurations
2. SystemD service files
3. Application code through the `utils/port_config.py` module

### Using in Development

When running the applications locally, you can:

1. Set the environment variables before starting the applications:
   ```bash
   export API_PORT=8005
   export NITTER_PORT=8085
   ```

2. Or modify the `.env` file directly.

### Using with Docker Compose

The Docker Compose files are already configured to use these environment variables:

```bash
# Start with default ports
docker-compose up -d

# Start with custom ports
API_PORT=8005 NITTER_PORT=8085 docker-compose up -d
```

This configuration ensures that you can run multiple instances of these applications on the same machine without port conflicts. 