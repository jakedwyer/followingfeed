import os
import dotenv

def load_env_variables():
    dotenv.load_dotenv()
    env_vars = {
        'bearer_token': os.getenv('Bearer'),
        'consumer_key': os.getenv('consumerKey'),
        'consumer_secret': os.getenv('consumerSecret'),
        'access_token': os.getenv('accessToken'),
        'access_token_secret': os.getenv('accessTokenSecret'),
        'list_id': os.getenv('list_id'),
        'cookie_path': os.getenv('cookie_path')
    }
    return env_vars
