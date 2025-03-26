# FollowFeed

A tool for tracking and analyzing social media accounts and their followers.

## Project Structure

The project has been reorganized for better maintainability:

```
followfeed/
├── config/               # Configuration files
├── data/                 # Data storage
├── docker/               # Docker-related files
│   ├── app/              # Main application Docker files
│   └── api/              # API service Docker files
├── logs/                 # Log files
├── scripts/              # Helper scripts
│   └── deployment/       # Deployment-specific scripts
├── src/                  # Source code
│   └── followfeed/       # Main package
│       ├── api/          # API-related code
│       ├── core/         # Core application logic
│       ├── scraping/     # Web scraping utilities
│       ├── twitter/      # Twitter-specific functionality
│       └── utils/        # Utility functions
└── tests/                # Test suite
```

## Installation

### Development Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/followfeed.git
   cd followfeed
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .  # Install the package in development mode
   ```

3. Copy the example environment file and edit it:
   ```
   cp .env.example .env
   ```

4. Edit `.env` with your credentials and configuration.

### Using Docker

1. Build and run using Docker Compose:
   ```
   cd docker
   docker compose up -d
   ```

## Usage

### Running the Application

```
python main.py
```

Or use the installed command:

```
followfeed
```

### Running the API Server

```
cd docker/api
docker compose up -d followfeed-api
```

Or use the provided script:

```
./scripts/run_api.sh
```

## Configuration

The application is configured using environment variables defined in the `.env` file.

## License

[Your License Here] 