import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, TypedDict

from pyairtable import Api
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv


# Define our own type for Airtable records
class AirtableRecord(TypedDict):
    id: str
    fields: Dict[str, Any]
    createdTime: str


# Define content types
class ContentTextValue(TypedDict):
    value: str


class ContentText(TypedDict):
    text: ContentTextValue
    type: str


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("twitter_analyzer.log"), logging.StreamHandler()],
)
logger = logging.getLogger("twitter_profile_analyzer")

# Load environment variables from .env file
load_dotenv()
logger.info("Environment variables loaded")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logger.info("OpenAI client initialized")

# Initialize Airtable client
AIRTABLE_API_KEY = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_ACCOUNTS_TABLE")

# Validate environment variables
for var_name, var_value in [
    ("AIRTABLE_TOKEN", AIRTABLE_API_KEY),
    ("AIRTABLE_BASE_ID", AIRTABLE_BASE_ID),
    ("AIRTABLE_ACCOUNTS_TABLE", AIRTABLE_TABLE_NAME),
]:
    if not var_value:
        logger.error(f"{var_name} environment variable not set")
        raise ValueError(f"{var_name} environment variable not set")

logger.info(
    f"Airtable configuration: BASE_ID={AIRTABLE_BASE_ID}, TABLE={AIRTABLE_TABLE_NAME}"
)
airtable = Api(api_key=AIRTABLE_API_KEY or "")  # Type assertion
table = airtable.table(
    base_id=AIRTABLE_BASE_ID or "", table_name=AIRTABLE_TABLE_NAME or ""
)  # Type assertion


async def get_recent_accounts() -> List[AirtableRecord]:
    """Get accounts created in the last 4 hours from Airtable."""
    cutoff_time = datetime.utcnow() - timedelta(hours=12)
    cutoff_str = cutoff_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    formula = f"CREATED_TIME() >= '{cutoff_str}'"

    logger.info(f"Querying Airtable with formula: {formula}")

    try:
        records = table.all(formula=formula)
        logger.info(f"Retrieved {len(records)} records from Airtable")
        if records:
            logger.debug(f"Sample record ID: {records[0]['id']}")
        return records
    except Exception as e:
        logger.error(f"Error retrieving records from Airtable: {str(e)}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def analyze_profile(profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a profile using OpenAI with web search capability."""
    username = profile_data.get("username", "unknown")
    logger.info(f"Starting analysis for profile: {username}")

    # Construct the prompt with profile data
    prompt_content = f"""Extract structured data on this entity:

    Twitter Profile:
    - Name: {profile_data.get('full_name', 'N/A')}
    - Posts: {profile_data.get('tweet_count', 'N/A')}
    - Followers: {profile_data.get('followers_count', 'N/A')}
    - Following: {profile_data.get('following_count', 'N/A')}
    - Location: {profile_data.get('location', 'N/A')}
    - Website: {profile_data.get('website', 'N/A')}
    
    Additional Info:
    - Description: {profile_data.get('description', 'N/A')}
    - Username: {username}
    - Date Analyzed: {datetime.utcnow().isoformat()}"""

    instructions = """You are a business analyst specialized in evaluating Twitter profiles 
            for investment potential. Analyze the provided profile data and use web search when 
            needed to verify or augment the information. Your analysis must be provided in JSON format
            with the following structure:
            {
                "profile": {
                    "name": "Business name or individual name if no business is attached", 
                    "description": "Detailed description based on Twitter bio and web search"
                },
                "website": "Business website if found during analysis",
                "investment_potential": {
                    "score": 1-10 rating of investment potential,
                    "justification": "Brief reasoning for the score based on profile data and search results"
                }
            }"""

    logger.debug(f"Prompt for {username}: {prompt_content}")

    try:
        logger.info(f"Sending request to OpenAI for {username}")

        # Use the Chat Completions API with web search capability and structured output
        response = client.chat.completions.create(
            model="gpt-4o-search-preview",
            web_search_options={"search_context_size": "medium"},
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "twitter_profile_analysis",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "profile": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                                "required": ["name", "description"],
                                "additionalProperties": False,
                            },
                            "website": {"type": "string"},
                            "investment_potential": {
                                "type": "object",
                                "properties": {
                                    "score": {"type": "integer"},
                                    "justification": {"type": "string"},
                                },
                                "required": ["score", "justification"],
                                "additionalProperties": False,
                            },
                        },
                        "required": ["profile", "investment_potential", "website"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt_content},
            ],
        )

        logger.info(f"Received response from OpenAI for {username}")

        # Process the response
        if response.choices and response.choices[0].message.content:
            try:
                # Check if the response was complete or cut off
                if response.choices[0].finish_reason == "length":
                    logger.warning(
                        f"Response was cut off due to max tokens for {username}"
                    )
                    return {
                        "error": "Response cut off due to max tokens",
                        "raw_response": response.choices[0].message.content,
                    }

                # Check if the response was filtered for content safety
                if response.choices[0].finish_reason == "content_filter":
                    logger.warning(
                        f"Response was filtered due to content safety for {username}"
                    )
                    return {
                        "error": "Response filtered for content safety",
                    }

                # Check for refusals
                if (
                    hasattr(response.choices[0].message, "refusal")
                    and response.choices[0].message.refusal
                ):
                    logger.warning(f"Response contained a refusal for {username}")
                    return {
                        "error": "Model refused to generate a response",
                        "refusal": response.choices[0].message.refusal,
                    }

                # Parse JSON content
                analysis = json.loads(response.choices[0].message.content)
                logger.info(f"Successfully parsed JSON response for {username}")
                return analysis
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON response for {username}: {e}")
                return {
                    "error": "Failed to parse JSON response",
                    "raw_response": response.choices[0].message.content,
                }
        else:
            logger.error(f"Empty response content for {username}")
            return {"error": "Empty response content"}

    except Exception as e:
        logger.error(
            f"Error in analyze_profile for {username}: {str(e)}", exc_info=True
        )
        return {"error": f"Analysis failed: {str(e)}"}


async def update_airtable_record(
    record_id: str, username: str, analysis: Dict[str, Any]
):
    """Update an Airtable record with analysis results."""
    try:
        # Extract score, handling potential missing data
        score = None
        if (
            "investment_potential" in analysis
            and "score" in analysis["investment_potential"]
        ):
            score = analysis["investment_potential"]["score"]

        # Update Airtable with analysis
        update_data: Dict[str, Any] = {
            "Score Justification": json.dumps(analysis, indent=2),
        }

        # Only include score if it exists
        if score is not None:
            update_data["Score"] = score

        table.update(record_id, update_data)
        logger.info(f"Successfully updated Airtable record for {username}")

    except Exception as e:
        logger.error(f"Error updating Airtable record for {username}: {str(e)}")


async def process_accounts():
    """Main function to process accounts from Airtable."""
    # Define field names based on the Airtable schema
    field_mapping = {
        "username": "Username",
        "full_name": "Full Name",
        "description": "Description",
        "tweet_count": "Tweet Count",
        "followers_count": "Followers Count",
        "following_count": "Following Count",
        "location": "Location",
        "website": "Website",
    }

    # Configure rate limiting from env if available
    rate_limit = int(os.getenv("AIRTABLE_RATE_LIMIT", "5"))
    batch_size = int(os.getenv("AIRTABLE_BATCH_SIZE", "10"))
    polling_interval = int(os.getenv("POLLING_INTERVAL_SECONDS", "300"))

    logger.info(
        f"Starting processing with rate limit: {rate_limit}/min, batch size: {batch_size}"
    )

    while True:
        try:
            # Get recent accounts
            accounts = await get_recent_accounts()
            logger.info(f"Found {len(accounts)} accounts to process")

            for i, account in enumerate(accounts):
                # Extract Twitter username from the record
                username = account["fields"].get(field_mapping["username"], "")
                record_id = account["id"]

                if not username:
                    logger.warning(f"Skipping record {record_id} - no username found")
                    continue

                # Extract profile data from Airtable record
                profile_data = {
                    field: account["fields"].get(field_mapping[field], "")
                    for field in field_mapping
                }

                logger.info(
                    f"Processing account {i+1}/{len(accounts)}: {username} (ID: {record_id})"
                )

                # Analyze profile
                try:
                    analysis = await analyze_profile(profile_data)
                    logger.info(
                        f"Analysis completed for {username}. Investment score: {analysis.get('investment_potential', {}).get('score', 'N/A')}"
                    )

                    # Update Airtable with analysis
                    await update_airtable_record(record_id, username, analysis)

                except Exception as e:
                    logger.error(
                        f"Error analyzing profile for {username}: {str(e)}",
                        exc_info=True,
                    )

                # Rate limiting
                wait_time = 60 / rate_limit
                logger.debug(
                    f"Rate limiting: waiting {wait_time} seconds before next request"
                )
                await asyncio.sleep(wait_time)

                # Process in batches if configured
                if (i + 1) % batch_size == 0 and i < len(accounts) - 1:
                    logger.info(f"Processed batch of {batch_size} accounts, pausing...")
                    await asyncio.sleep(10)  # Pause between batches

            # Wait before next polling cycle
            logger.info(
                f"Completed processing cycle, waiting {polling_interval} seconds..."
            )
            await asyncio.sleep(polling_interval)

        except Exception as e:
            logger.error(f"Error in process_accounts: {str(e)}", exc_info=True)
            logger.info("Waiting 60 seconds before retry due to error")
            await asyncio.sleep(60)  # Wait 1 minute on error


if __name__ == "__main__":
    logger.info("Starting Twitter profile analyzer...")
    try:
        asyncio.run(process_accounts())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error in main process: {str(e)}", exc_info=True)
