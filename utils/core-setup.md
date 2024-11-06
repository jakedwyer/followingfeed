# Twitter Network Analysis Project Setup Guide

## Project Overview
This Python project analyzes Twitter/X social networks by tracking followers and their following relationships. The main objectives are to:

1. Fetch members from a specified Twitter list
2. Track these members in an Airtable "Followers" table
3. Collect and store all accounts followed by these members in an Airtable "Accounts" table
4. Maintain historical following relationship data
5. Enrich account data with profile information

## Core Components

### Main Script (main.py)
The central orchestrator that:
- Manages the overall data collection flow
- Handles Airtable record creation and updates
- Implements rate limiting and error handling
- Maintains process locking for scheduled runs
- Provides comprehensive logging

### Key Dependencies
- `selenium`: Web scraping Twitter data
- `requests`: Airtable API interactions
- `python-dotenv`: Environment configuration
- `logging`: Application monitoring

### Directory Structure
```
/root/followfeed/
├── main.py                         # Main orchestration script
├── utils/
│   ├── airtable.py                # Airtable API functions
│   ├── config.py                  # Environment configuration
│   ├── logging_setup.py           # Logging configuration
│   └── core-setup.md             # Project documentation
├── twitter/
│   ├── twitter.py                 # Twitter API functions
│   └── twitter_account_details.py # Profile data collection
├── scraping/
│   └── scraping.py               # Web scraping functions
├── output/                       # CSV data storage
│   ├── BigBrainKasey/
│   │   └── cumulative_follows.csv
│   ├── FrankieIsLost/
│   │   └── cumulative_follows.csv
│   ├── SOLBigBrain/
│   │   └── cumulative_follows.csv
│   └── _JonahB_/
│       └── cumulative_follows.csv
├── scrape_empty_accounts.py      # Profile enrichment script
└── update_airtable_json.py      # Schema update utility
```

## Environment Variables (.env)
```

# Twitter API Authentication
TWITTER_API_KEY=                   # Twitter API key
TWITTER_API_SECRET=                # Twitter API secret
TWITTER_BEARER_TOKEN=              # Twitter Bearer token
TWITTER_ACCESS_TOKEN=              # Twitter access token
TWITTER_ACCESS_TOKEN_SECRET=       # Twitter access token secret

# Twitter Client Configuration
CLIENT_ID=                         # Twitter client ID
CLIENT_SECRET=                     # Twitter client secret
LIST_ID=                          # Target Twitter list ID
COOKIE_PATH=                       # Path to stored cookies

# Airtable Configuration
AIRTABLE_BASE_ID=                 # Airtable base identifier
AIRTABLE_TOKEN=                   # Airtable API token
AIRTABLE_FOLLOWERS_TABLE=         # Followers table ID
AIRTABLE_ACCOUNTS_TABLE=          # Accounts table ID
AIRTABLE_API_ENDPOINT=            # Airtable API endpoint
AIRTABLE_BATCH_SIZE=              # Records per batch
AIRTABLE_RATE_LIMIT=              # API rate limit

# Field Mappings
FIELD_USERNAME=                   # Username field identifier
FIELD_ACCOUNT=                    # Account field identifier
FIELD_ACCOUNT_ID=                 # Account ID field identifier
FIELD_FOLLOWED_ACCOUNTS=          # Following field identifier

# Runtime Configuration
LOCK_FILE=                        # Process lock file path
VENV_PATH=                        # Virtual environment path
LOG_FILE=                         # Log file location
JSON_FILE_PATH=                   # Optional JSON storage path
```

## Airtable Schema

### Accounts Table (tblJCXhcrCxDUJR3F)
Primary fields:
- Username (Single Line Text)
- Full Name (Single Line Text)
- Description (Rich Text)
- Research (Checkbox)
- Enriched (Checkbox)
- Followers (Multiple Record Links)
- Tweet Count (Number)
- Listed Count (Number)
- Followers Count (Number)
- Created At (DateTime)
- Account ID (Single Line Text)

### Followers Table (tbl7bEfNVnCEQvUkT)
Primary fields:
- Username (Single Line Text)
- Description (Multiline Text)
- Full Name (Single Line Text)
- Created At (Date)
- Account (Multiple Record Links)
- Account ID (Single Line Text)
- Category (Multiple Select)

### Changes Table (tbl7mXYq4ms6FjPkn)
Primary fields:
- Change (Auto Number)
- Account (Multiple Record Links)
- New Follower Count (Number)
- Created (Created Time)

## Data Relationships
- Followers table links to Accounts table via "Account" field
- Accounts table links to Followers table via "Followers" field
- Changes table tracks historical data linked to Accounts

## Key Processes

1. **List Member Processing**
   - Fetches Twitter list members
   - Creates/updates Follower records
   - Maintains member metadata

2. **Following Collection**
   - Scrapes following lists for each member
   - Creates new Account records as needed
   - Updates following relationships

3. **Profile Enrichment**
   - Collects detailed profile information
   - Updates Account records with metadata
   - Tracks changes over time

## Error Handling & Monitoring
- Comprehensive logging to main.log
- Process locking prevents concurrent execution
- Rate limit monitoring for APIs
- Batch processing with error recovery
- Exception handling and reporting

## Deployment
- Hosted on Digital Ocean
- Scheduled nightly execution at midnight EST
- Process locking mechanism
- Logging for debugging and monitoring

## Important Considerations
- Respect Twitter API rate limits
- Monitor Airtable API quotas
- Maintain web scraping reliability
- Ensure data consistency
- Implement proper error recovery