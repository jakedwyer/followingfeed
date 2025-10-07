# FollowFeed

**Automated Twitter Profile Analysis & Follow Tracking System**

FollowFeed is a comprehensive tool for tracking Twitter follows, enriching profile data, and analyzing Twitter accounts using AI. It integrates with Airtable for data storage and provides automated profile enrichment through web scraping and API calls.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

### Core Functionality
- 🔄 **Automated Follow Tracking**: Monitor Twitter accounts and track their following lists
- 📊 **Profile Enrichment**: Automatically fetch and update profile data (bio, followers count, location, etc.)
- 🤖 **AI-Powered Analysis**: Use OpenAI GPT-4 to analyze profiles for investment potential
- 📈 **Airtable Integration**: Store and manage all data in Airtable with automatic syncing
- 🔍 **Web Scraping**: Fallback to Nitter scraping when API limits are reached
- ⚡ **Async Processing**: Efficient batch processing with rate limiting
- 🔐 **Cookie-Based Authentication**: Support for authenticated Twitter scraping

### Components

1. **main.py** - Main orchestration script that tracks follows and updates Airtable
2. **fetch_profile.py** - Enriches account data using Twitter API
3. **scrape_empty_accounts.py** - Web scraping fallback for profiles without data
4. **twitter_profile_analyzer.py** - AI-powered profile analysis using OpenAI

## Installation

### Prerequisites

- Python 3.9 or higher
- Google Chrome (for Selenium web scraping)
- ChromeDriver (matching your Chrome version)
- Airtable account with API access
- Twitter API credentials (optional, for API-based enrichment)
- OpenAI API key (optional, for AI analysis)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/followfeed.git
   cd followfeed
   ```

2. **Install dependencies**
   
   Using UV (recommended):
   ```bash
   pip install uv
   uv pip install -r requirements.txt
   ```
   
   Or using pip:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   nano .env
   ```

4. **Set up Airtable**
   
   Create two tables in your Airtable base:
   
   **Followers Table** (stores accounts you're tracking):
   - `Username` (Single line text, primary field)
   - `Account` (Link to Accounts table, multiple records)
   
   **Accounts Table** (stores all Twitter accounts):
   - `Username` (Single line text, primary field)
   - `Full Name` (Single line text)
   - `Description` (Long text)
   - `Location` (Single line text)
   - `Website` (URL)
   - `Created At` (Date)
   - `Followers Count` (Number)
   - `Following Count` (Number)
   - `Tweet Count` (Number)
   - `Listed Count` (Number)
   - `Account ID` (Single line text)
   - `Followers` (Link to Followers table, multiple records)
   - `Analysis` (Long text, for AI analysis results)
   - `LastAnalyzed` (Date)

5. **Install ChromeDriver**
   ```bash
   # On Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install -y chromium-browser chromium-chromedriver
   
   # On macOS
   brew install chromedriver
   ```

6. **Set up cookies (for authenticated scraping)**
   
   Export your Twitter cookies to `cookies.pkl` using a browser extension or manual process.

## Usage

### Track Twitter Follows

Run the main script to track follows for all accounts in your Followers table:

```bash
python main.py
```

This will:
1. Fetch all accounts from your Followers table in Airtable
2. For each account, scrape their Twitter following list
3. Create/update Account records for each followed account
4. Update the links between Followers and Accounts
5. Enrich new accounts with profile data

### Enrich Profile Data via API

Use the Twitter API to enrich existing accounts:

```bash
python fetch_profile.py
```

This will fetch complete profile data for accounts missing information.

### Scrape Empty Accounts

Use web scraping (Nitter) to fill in missing profile data:

```bash
python scrape_empty_accounts.py
```

### AI Profile Analysis

Analyze Twitter profiles for investment potential using OpenAI:

```bash
python twitter_profile_analyzer.py
```

This will:
1. Poll Airtable for profiles without analysis
2. Use GPT-4 with web search to analyze each profile
3. Score investment potential (1-10)
4. Update Airtable with analysis results

### Automated Execution

Set up a cron job for automated tracking:

```bash
# Edit crontab
crontab -e

# Add this line to run every 6 hours
0 */6 * * * cd /path/to/followfeed && /usr/bin/python main.py >> logs/cron.log 2>&1
```

Or use the provided shell script:

```bash
chmod +x run_followfeed.sh
./run_followfeed.sh
```

## Configuration

### Environment Variables

All configuration is done through environment variables in `.env`. See `.env.example` for all available options.

#### Required Variables

```env
# Airtable
AIRTABLE_TOKEN=your_airtable_token
AIRTABLE_BASE_ID=your_base_id
AIRTABLE_FOLLOWERS_TABLE=your_followers_table_id
AIRTABLE_ACCOUNTS_TABLE=your_accounts_table_id

# For cookie-based scraping
COOKIE_PATH=cookies.pkl
```

#### Optional Variables

```env
# Twitter API (for fetch_profile.py)
TWITTER_BEARER_TOKEN=your_bearer_token

# OpenAI (for twitter_profile_analyzer.py)
OPENAI_API_KEY=your_openai_key

# Performance tuning
AIRTABLE_BATCH_SIZE=10
AIRTABLE_RATE_LIMIT=5
```

## Architecture

### Data Flow

```
Followers Table (Airtable)
    ↓
main.py → Twitter Scraping → Get Following Lists
    ↓
Accounts Table (Airtable) ← Create/Update Records
    ↓
fetch_profile.py → Twitter API → Enrich Data
    ↓
scrape_empty_accounts.py → Nitter Scraping → Fill Gaps
    ↓
twitter_profile_analyzer.py → OpenAI GPT-4 → AI Analysis
```

### Key Modules

- **utils/airtable.py** - Airtable API interactions with caching
- **utils/config.py** - Environment variable loading
- **utils/logging_setup.py** - Logging configuration
- **utils/user_data.py** - Local JSON caching for user data
- **scraping/scraping.py** - Selenium-based Twitter scraping
- **twitter/twitter.py** - Twitter API wrapper
- **twitter/nitter_scraper.py** - Nitter-based web scraping
- **twitter/profile_analyzer.py** - OpenAI profile analysis

## Deployment

### Docker Support

Build and run with Docker:

```bash
# Build the image
docker build -t followfeed .

# Run the container
docker run -d \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  followfeed
```

### Production Considerations

1. **Rate Limiting**: Twitter has strict rate limits. Use delays and respect limits.
2. **Caching**: The system caches Airtable data locally to reduce API calls.
3. **Error Handling**: All operations have retry logic and error handling.
4. **Logging**: Comprehensive logging to `logs/main.log` with rotation.
5. **Concurrency**: Uses async/await for efficient batch processing.

## Troubleshooting

### Common Issues

**ChromeDriver version mismatch**
```bash
# Check versions
google-chrome --version
chromedriver --version

# Update ChromeDriver
pip install --upgrade webdriver-manager
```

**Airtable rate limits**
- Reduce `AIRTABLE_BATCH_SIZE` in `.env`
- Increase delays between requests

**Cookie expiration**
- Re-export your Twitter cookies
- Ensure cookies.pkl is up to date

**Missing profile data**
- Run `scrape_empty_accounts.py` after `main.py`
- Check that your cookies are valid

## Development

### Project Structure

```
followfeed/
├── main.py                          # Main orchestration script
├── fetch_profile.py                 # Twitter API profile enrichment
├── scrape_empty_accounts.py         # Nitter scraping fallback
├── twitter_profile_analyzer.py      # AI profile analysis
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template
├── run_followfeed.sh               # Execution wrapper script
├── utils/                          # Utility modules
│   ├── airtable.py                # Airtable API wrapper
│   ├── config.py                  # Configuration loader
│   ├── logging_setup.py           # Logging setup
│   ├── user_data.py               # User data caching
│   ├── lock.py                    # File locking
│   ├── webhook.py                 # Webhook support
│   └── port_config.py             # Port configuration
├── twitter/                        # Twitter integrations
│   ├── twitter.py                 # Twitter API client
│   ├── twitter_api.py             # API wrapper
│   ├── nitter_scraper.py          # Nitter scraping
│   ├── profile_analyzer.py        # OpenAI analysis
│   ├── profile_analyzer_ollama.py # Ollama analysis
│   ├── driver_init.py             # WebDriver init
│   ├── webdriver_pool.py          # WebDriver pooling
│   └── twitter_account_details.py # Account details
├── scraping/                       # Web scraping
│   └── scraping.py                # Selenium scraping logic
└── tests/                          # Test suite
    ├── test_airtable_auth.py
    ├── test_profile_analyzer.py
    └── ...
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_airtable_auth.py

# Run with coverage
pytest --cov=. --cov-report=html
```

### Code Style

This project follows PEP 8 style guidelines. Format code with:

```bash
# Install formatters
pip install black isort

# Format code
black .
isort .
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational and research purposes. Please:
- Respect Twitter's Terms of Service
- Be mindful of rate limits
- Don't use for spam or harassment
- Follow data privacy regulations

## Support

For issues and questions:
- 📫 Open an issue on GitHub
- 📖 Check the [documentation](https://github.com/yourusername/followfeed/wiki)
- 💬 Join discussions in GitHub Discussions

## Acknowledgments

- Built with [Selenium](https://www.selenium.dev/) for web scraping
- Uses [Airtable](https://airtable.com/) for data storage
- Powered by [OpenAI GPT-4](https://openai.com/) for AI analysis
- Inspired by the need for better Twitter follow tracking

---

**Made with ❤️ by the FollowFeed community**
