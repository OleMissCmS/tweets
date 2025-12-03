"""
Multi-scraper abstraction layer with fallback mechanism
Supports multiple Twitter scraping libraries with automatic failover
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import datetime
import logging
import os
import asyncio

logger = logging.getLogger(__name__)


class TweetScraper(ABC):
    """Base class for all tweet scrapers"""
    
    @abstractmethod
    def scrape_user_tweets(self, username: str, start_date: Optional[datetime.datetime] = None, 
                          end_date: Optional[datetime.datetime] = None, 
                          max_tweets: int = 1000) -> List[Dict]:
        """Scrape tweets for a user. Returns list of tweet dicts."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this scraper"""
        pass
    
    def is_available(self) -> bool:
        """Check if this scraper is available/installed"""
        return True


class TwitterAPIScraper(TweetScraper):
    """Twitter API v2 implementation using official X Developer Platform SDK (xdk-python) - PRIMARY METHOD"""
    
    def get_name(self) -> str:
        return "Twitter API v2 (xdk)"
    
    def is_available(self) -> bool:
        try:
            from xdk import Client
            # Check for OAuth 1.0a credentials (preferred)
            api_key = os.getenv('TWITTER_API_KEY', '').strip()
            api_secret = os.getenv('TWITTER_API_SECRET', '').strip()
            access_token = os.getenv('TWITTER_ACCESS_TOKEN', '').strip()
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET', '').strip()
            
            # Check for Bearer Token (OAuth 2.0 App-only)
            bearer_token = os.getenv('TWITTER_BEARER_TOKEN', '').strip()
            
            # Check for OAuth 2.0 Client ID/Secret (for future user context features)
            client_id = os.getenv('TWITTER_CLIENT_ID', '').strip()
            client_secret = os.getenv('TWITTER_CLIENT_SECRET', '').strip()
            client_oauth2_secret = os.getenv('TWITTER_CLIENT_OAUTH2', '').strip()
            
            # Available if we have OAuth 1.0a OR Bearer Token OR OAuth 2.0 Client credentials
            return bool((api_key and api_secret and access_token and access_token_secret) or 
                       bearer_token or 
                       (client_id and client_secret) or
                       (client_id and client_oauth2_secret))
        except ImportError:
            return False
    
    def scrape_user_tweets(self, username: str, start_date=None, end_date=None, max_tweets=1000):
        from xdk import Client
        
        # Authentication priority: OAuth 1.0a > Bearer Token > OAuth 2.0 Client ID/Secret
        api_key = os.getenv('TWITTER_API_KEY', '').strip()
        api_secret = os.getenv('TWITTER_API_SECRET', '').strip()
        access_token = os.getenv('TWITTER_ACCESS_TOKEN', '').strip()
        access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET', '').strip()
        
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN', '').strip()
        
        client_id = os.getenv('TWITTER_CLIENT_ID', '').strip()
        client_secret = os.getenv('TWITTER_CLIENT_SECRET', '').strip()
        client_oauth2_secret = os.getenv('TWITTER_CLIENT_OAUTH2', '').strip()
        
        # Initialize client - try OAuth 1.0a first, then Bearer Token, then OAuth 2.0
        try:
            if api_key and api_secret and access_token and access_token_secret:
                logger.info("Using OAuth 1.0a authentication with xdk")
                # xdk-python uses OAuth1User for OAuth 1.0a
                try:
                    from xdk.auth import OAuth1User
                    auth = OAuth1User(
                        consumer_key=api_key,
                        consumer_secret=api_secret,
                        access_token=access_token,
                        access_token_secret=access_token_secret
                    )
                    client = Client(auth=auth)
                except ImportError:
                    # Fallback: try direct initialization if OAuth1User doesn't exist
                    client = Client(
                        api_key=api_key,
                        api_secret=api_secret,
                        access_token=access_token,
                        access_token_secret=access_token_secret
                    )
            elif bearer_token:
                logger.info("Using Bearer Token authentication (OAuth 2.0 App-only) with xdk")
                client = Client(bearer_token=bearer_token)
            elif client_id and (client_secret or client_oauth2_secret):
                logger.info("Using OAuth 2.0 Client ID/Secret authentication with xdk")
                # Use OAuth 2.0 secret if available, otherwise fall back to regular client secret
                oauth2_secret = client_oauth2_secret if client_oauth2_secret else client_secret
                # Note: OAuth 2.0 Client ID/Secret typically requires PKCE flow for user context
                # For app-only operations, Bearer Token is preferred
                # This is here for future user context features
                try:
                    from xdk.auth import OAuth2ClientCredentials
                    auth = OAuth2ClientCredentials(
                        client_id=client_id,
                        client_secret=oauth2_secret
                    )
                    client = Client(auth=auth)
                except ImportError:
                    # Fallback: try direct initialization
                    client = Client(
                        client_id=client_id,
                        client_secret=oauth2_secret
                    )
            else:
                raise Exception("Twitter API credentials not configured. Set TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, and TWITTER_ACCESS_TOKEN_SECRET (or TWITTER_BEARER_TOKEN, or TWITTER_CLIENT_ID with TWITTER_CLIENT_SECRET/TWITTER_CLIENT_OAUTH2).")
        except Exception as e:
            logger.error(f"Failed to initialize xdk client: {e}")
            raise Exception(f"Failed to initialize Twitter API client: {e}")
        
        try:
            # Get user by username to get user ID
            # xdk-python uses client.users.get() or similar
            try:
                # Try common API patterns for getting user
                if hasattr(client, 'users') and hasattr(client.users, 'get'):
                    user_response = client.users.get(usernames=[username])
                elif hasattr(client, 'get_user'):
                    user_response = client.get_user(username=username)
                else:
                    # Try direct attribute access
                    user_response = client.users.get(usernames=[username])
                
                # Extract user data from response
                if not user_response:
                    raise Exception(f"User '{username}' not found")
                
                user_data = None
                if hasattr(user_response, 'data'):
                    data = user_response.data
                    user_data = data[0] if isinstance(data, list) and len(data) > 0 else data
                elif isinstance(user_response, dict):
                    user_data = user_response.get('data', [])
                    user_data = user_data[0] if isinstance(user_data, list) and len(user_data) > 0 else user_data
                else:
                    user_data = user_response
                
                if not user_data:
                    raise Exception(f"User '{username}' not found")
                
                # Extract user ID
                user_id = None
                if hasattr(user_data, 'id'):
                    user_id = str(user_data.id)
                elif isinstance(user_data, dict):
                    user_id = str(user_data.get('id', ''))
                else:
                    user_id = str(user_data)
                
                if not user_id:
                    raise Exception(f"Could not extract user ID for '{username}'")
                    
            except Exception as e:
                logger.error(f"Error getting user '{username}': {e}")
                raise Exception(f"Unable to get user '{username}': {e}")
            
            tweets = []
            next_token = None
            tweet_count = 0
            
            # Paginate through tweets
            while tweet_count < max_tweets:
                try:
                    # Calculate how many tweets to fetch in this batch
                    max_results = min(100, max_tweets - tweet_count)  # API max is 100 per request
                    
                    # Get user's tweets using xdk
                    # xdk-python API: client.tweets.get_user_tweets() or client.posts.get_user_tweets()
                    try:
                        # Try tweets API first (most common)
                        if hasattr(client, 'tweets') and hasattr(client.tweets, 'get_user_tweets'):
                            response = client.tweets.get_user_tweets(
                                id=user_id,
                                max_results=max_results,
                                pagination_token=next_token,
                                tweet_fields=['created_at', 'public_metrics', 'author_id', 'conversation_id', 'in_reply_to_user_id', 'referenced_tweets']
                            )
                        elif hasattr(client, 'posts') and hasattr(client.posts, 'get_user_tweets'):
                            # Alternative: posts API
                            response = client.posts.get_user_tweets(
                                id=user_id,
                                max_results=max_results,
                                pagination_token=next_token
                            )
                        elif hasattr(client, 'tweets') and hasattr(client.tweets, 'get'):
                            # Alternative: tweets.get with user_id parameter
                            response = client.tweets.get(
                                id=user_id,
                                max_results=max_results,
                                pagination_token=next_token
                            )
                        else:
                            # Last resort: try to find the method dynamically
                            raise AttributeError("Could not find get_user_tweets method in xdk client")
                    except AttributeError as e:
                        logger.error(f"xdk API method not found: {e}")
                        raise Exception(f"xdk-python API structure may differ. Please check xdk-python documentation. Error: {e}")
                    except Exception as e:
                        logger.error(f"Error calling xdk API: {e}")
                        raise
                    
                    # Extract data from response
                    if not hasattr(response, 'data') or not response.data:
                        break  # No more tweets
                    
                    tweet_list = response.data if isinstance(response.data, list) else [response.data]
                    
                    hit_date_limit = False
                    for tweet in tweet_list:
                        # Date filtering
                        tweet_date = None
                        if hasattr(tweet, 'created_at'):
                            tweet_date = tweet.created_at
                        elif isinstance(tweet, dict):
                            tweet_date = tweet.get('created_at')
                        
                        if not tweet_date:
                            continue
                            
                        if isinstance(tweet_date, str):
                            tweet_date = datetime.datetime.fromisoformat(tweet_date.replace('Z', '+00:00'))
                        elif not isinstance(tweet_date, datetime.datetime):
                            continue
                        
                        # Ensure timezone aware
                        if tweet_date.tzinfo is None:
                            tweet_date = tweet_date.replace(tzinfo=datetime.timezone.utc)
                        
                        if start_date and tweet_date < start_date:
                            continue
                        if end_date and tweet_date > end_date:
                            # Since tweets are in reverse chronological order, we've gone past the end date
                            hit_date_limit = True
                            break
                        
                        # Determine tweet type
                        is_retweet = False
                        is_reply = False
                        is_quote = False
                        
                        # Check referenced_tweets
                        ref_tweets = None
                        if hasattr(tweet, 'referenced_tweets'):
                            ref_tweets = tweet.referenced_tweets
                        elif isinstance(tweet, dict):
                            ref_tweets = tweet.get('referenced_tweets')
                        
                        if ref_tweets:
                            for ref in (ref_tweets if isinstance(ref_tweets, list) else [ref_tweets]):
                                ref_type = ref.type if hasattr(ref, 'type') else ref.get('type', '')
                                if ref_type == 'retweeted':
                                    is_retweet = True
                                elif ref_type == 'quoted':
                                    is_quote = True
                        
                        # Check if reply
                        in_reply_to = None
                        if hasattr(tweet, 'in_reply_to_user_id'):
                            in_reply_to = tweet.in_reply_to_user_id
                        elif isinstance(tweet, dict):
                            in_reply_to = tweet.get('in_reply_to_user_id')
                        
                        if in_reply_to:
                            is_reply = True
                        
                        # Get metrics
                        metrics = {}
                        if hasattr(tweet, 'public_metrics'):
                            metrics = tweet.public_metrics
                        elif isinstance(tweet, dict):
                            metrics = tweet.get('public_metrics', {})
                        
                        # Get tweet ID and text
                        tweet_id = str(tweet.id if hasattr(tweet, 'id') else tweet.get('id', ''))
                        tweet_text = tweet.text if hasattr(tweet, 'text') else tweet.get('text', '')
                        
                        tweets.append({
                            'id': tweet_id,
                            'url': f"https://twitter.com/{username}/status/{tweet_id}",
                            'date': tweet_date.isoformat(),
                            'content': tweet_text or '',
                            'user': username,
                            'reply_count': metrics.get('reply_count', 0) if isinstance(metrics, dict) else (metrics.reply_count if hasattr(metrics, 'reply_count') else 0),
                            'retweet_count': metrics.get('retweet_count', 0) if isinstance(metrics, dict) else (metrics.retweet_count if hasattr(metrics, 'retweet_count') else 0),
                            'like_count': metrics.get('like_count', 0) if isinstance(metrics, dict) else (metrics.like_count if hasattr(metrics, 'like_count') else 0),
                            'quote_count': metrics.get('quote_count', 0) if isinstance(metrics, dict) else (metrics.quote_count if hasattr(metrics, 'quote_count') else 0),
                            'is_retweet': is_retweet,
                            'is_reply': is_reply,
                            'is_quote': is_quote,
                        })
                        
                        tweet_count += 1
                        if tweet_count >= max_tweets:
                            break
                    
                    # If we hit date limit, stop paginating
                    if hit_date_limit:
                        break
                    
                    # Check for next page
                    meta = None
                    if hasattr(response, 'meta'):
                        meta = response.meta
                    elif isinstance(response, dict):
                        meta = response.get('meta')
                    
                    if meta:
                        next_token = meta.get('next_token') if isinstance(meta, dict) else (meta.next_token if hasattr(meta, 'next_token') else None)
                        if not next_token:
                            break  # No more pages
                    else:
                        break  # No more pages
                        
                except Exception as e:
                    error_msg = str(e)
                    if '429' in error_msg or 'rate limit' in error_msg.lower():
                        logger.warning("Twitter API: Rate limit hit, waiting...")
                        raise Exception("Rate limit exceeded. Please try again later.")
                    elif '401' in error_msg or 'unauthorized' in error_msg.lower():
                        raise Exception("Twitter API authentication failed. Check your credentials.")
                    elif '404' in error_msg or 'not found' in error_msg.lower():
                        raise Exception(f"User '{username}' not found or account is private.")
                    else:
                        logger.error(f"Twitter API error: {e}")
                        raise
            
            return tweets
            
        except Exception as e:
            logger.error(f"Twitter API scraping error: {e}")
            raise


class SnscrapeScraper(TweetScraper):
    """snscrape implementation - primary scraper"""
    
    def get_name(self) -> str:
        return "snscrape"
    
    def is_available(self) -> bool:
        try:
            from snscrape.modules.twitter import TwitterUserScraper
            return True
        except ImportError:
            return False
    
    def scrape_user_tweets(self, username: str, start_date=None, end_date=None, max_tweets=1000):
        from snscrape.modules.twitter import TwitterUserScraper
        
        tweets = []
        scraper = TwitterUserScraper(username)
        count = 0
        
        for tweet in scraper.get_items():
            # Date filtering
            if start_date and tweet.date < start_date:
                continue
            if end_date and tweet.date > end_date:
                break
            
            # Convert tweet to dict
            tweet_data = {
                'id': str(tweet.id),
                'url': tweet.url,
                'date': tweet.date.isoformat(),
                'content': tweet.rawContent,
                'user': tweet.user.username if hasattr(tweet.user, 'username') else str(tweet.user),
                'reply_count': tweet.replyCount,
                'retweet_count': tweet.retweetCount,
                'like_count': tweet.likeCount,
                'quote_count': tweet.quoteCount,
                'is_retweet': tweet.retweetedTweet is not None,
                'is_reply': tweet.inReplyToTweetId is not None,
                'is_quote': tweet.quotedTweet is not None,
            }
            
            tweets.append(tweet_data)
            count += 1
            
            if count >= max_tweets:
                break
        
        return tweets


class ScweetScraper(TweetScraper):
    """Scweet implementation - alternative scraper"""
    
    def get_name(self) -> str:
        return "Scweet"
    
    def is_available(self) -> bool:
        try:
            from Scweet.scweet import scrape
            logger.info("Scweet: Successfully imported")
            return True
        except ImportError as e:
            logger.warning(f"Scweet: Import failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Scweet: Unexpected error: {e}")
            return False
    
    def scrape_user_tweets(self, username: str, start_date=None, end_date=None, max_tweets=1000):
        from Scweet.scweet import scrape
        import pandas as pd
        
        # Scweet uses different parameters
        # Note: Scweet may require authentication or have different API
        try:
            # Scweet scrapes by search query, so we use "from:username"
            data = scrape(
                words=[f"from:{username}"],
                since=start_date.strftime("%Y-%m-%d") if start_date else None,
                until=end_date.strftime("%Y-%m-%d") if end_date else None,
                limit=max_tweets,
                display_type="Top",  # or "Latest"
                lang="en"
            )
            
            tweets = []
            if isinstance(data, pd.DataFrame) and not data.empty:
                for _, row in data.iterrows():
                    tweet_date = pd.to_datetime(row.get('Timestamp', row.get('Datetime', None)))
                    if start_date and tweet_date < start_date:
                        continue
                    if end_date and tweet_date > end_date:
                        continue
                    
                    tweets.append({
                        'id': str(row.get('Tweet Id', '')),
                        'url': row.get('Tweet URL', f"https://twitter.com/{username}/status/{row.get('Tweet Id', '')}"),
                        'date': tweet_date.isoformat() if tweet_date else datetime.datetime.now().isoformat(),
                        'content': row.get('Text', row.get('Tweet', '')),
                        'user': username,
                        'reply_count': int(row.get('Replies', 0)),
                        'retweet_count': int(row.get('Retweets', 0)),
                        'like_count': int(row.get('Likes', 0)),
                        'quote_count': int(row.get('Quote Tweets', 0)),
                        'is_retweet': 'RT @' in str(row.get('Text', '')),
                        'is_reply': bool(row.get('Reply to', '')),
                        'is_quote': bool(row.get('Quote URL', '')),
                    })
            
            return tweets
        except Exception as e:
            logger.error(f"Scweet scraping error: {e}")
            raise


class TweeterPyScraper(TweetScraper):
    """TweeterPy implementation - alternative scraper
    
    Note: TweeterPy has strict beautifulsoup4 dependency (4.12.2) that conflicts
    with Scweet (4.12.3). This scraper may not be available if there are
    dependency conflicts.
    """
    
    def get_name(self) -> str:
        return "TweeterPy"
    
    def is_available(self) -> bool:
        try:
            from tweeterpy import TweeterPy
            return True
        except (ImportError, Exception) as e:
            logger.debug(f"TweeterPy not available: {e}")
            return False
    
    def scrape_user_tweets(self, username: str, start_date=None, end_date=None, max_tweets=1000):
        from tweeterpy import TweeterPy
        
        tp = TweeterPy()
        
        # TweeterPy API may vary - adjust based on actual library
        try:
            user_tweets = tp.get_user_tweets(username, count=max_tweets)
            
            tweets = []
            for tweet in user_tweets:
                tweet_date = datetime.datetime.fromisoformat(
                    tweet.get('created_at', '').replace('Z', '+00:00')
                ) if tweet.get('created_at') else datetime.datetime.now(datetime.timezone.utc)
                
                if start_date and tweet_date < start_date:
                    continue
                if end_date and tweet_date > end_date:
                    continue
                
                tweets.append({
                    'id': str(tweet.get('id', '')),
                    'url': tweet.get('url', f"https://twitter.com/{username}/status/{tweet.get('id', '')}"),
                    'date': tweet_date.isoformat(),
                    'content': tweet.get('text', tweet.get('full_text', '')),
                    'user': username,
                    'reply_count': int(tweet.get('reply_count', 0)),
                    'retweet_count': int(tweet.get('retweet_count', 0)),
                    'like_count': int(tweet.get('favorite_count', tweet.get('like_count', 0))),
                    'quote_count': int(tweet.get('quote_count', 0)),
                    'is_retweet': tweet.get('retweeted', False) or 'retweeted_status' in tweet,
                    'is_reply': bool(tweet.get('in_reply_to_status_id')),
                    'is_quote': bool(tweet.get('quoted_status_id')),
                })
            
            return tweets
        except Exception as e:
            logger.error(f"TweeterPy scraping error: {e}")
            raise


class TwikitScraper(TweetScraper):
    """Twikit implementation - requires authentication"""
    
    def __init__(self):
        self.client = None
        self.cookies_file = 'twikit_cookies.json'
        self._initialized = False
    
    def get_name(self) -> str:
        return "Twikit"
    
    def is_available(self) -> bool:
        try:
            from twikit import Client
            # Check if credentials are available
            return bool(os.getenv('TWITTER_USERNAME') and 
                      os.getenv('TWITTER_EMAIL') and 
                      os.getenv('TWITTER_PASSWORD'))
        except ImportError:
            return False
    
    async def _ensure_authenticated(self):
        """Ensure client is authenticated with improved error handling"""
        if self._initialized and self.client:
            return
        
        from twikit import Client
        import json
        
        self.client = Client('en-US')
        
        # Try to load cookies first
        if os.path.exists(self.cookies_file):
            try:
                import aiofiles
                async with aiofiles.open(self.cookies_file, 'r') as f:
                    cookies = json.loads(await f.read())
                    self.client.set_cookies(cookies)
                    # Test if cookies are still valid
                    try:
                        await self.client.get_user_by_screen_name('twitter')
                        self._initialized = True
                        logger.info("Twikit: Loaded valid cookies")
                        return
                    except Exception as e:
                        logger.warning(f"Twikit: Cookies expired, re-authenticating: {e}")
                        # Cookies expired, need to re-authenticate
                        pass
            except Exception as e:
                logger.warning(f"Twikit: Failed to load cookies: {e}")
        
        # Authenticate with credentials
        username = os.getenv('TWITTER_USERNAME', '').strip()
        email = os.getenv('TWITTER_EMAIL', '').strip()
        password = os.getenv('TWITTER_PASSWORD', '').strip()
        
        if not all([username, email, password]):
            raise Exception("Twikit credentials not configured. Set TWITTER_USERNAME, TWITTER_EMAIL, and TWITTER_PASSWORD environment variables.")
        
        logger.info("Twikit: Authenticating with credentials...")
        
        # Try primary authentication method
        try:
            await self.client.login(
                auth_info_1=username,  # Username
                auth_info_2=email,      # Email
                password=password
            )
            logger.info("Twikit: Authentication successful")
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Twikit: Standard auth failed: {error_msg}")
            
            # Try alternative authentication methods
            try:
                # Some Twikit versions might use different parameter names
                await self.client.login(
                    username=username,
                    email=email,
                    password=password
                )
                logger.info("Twikit: Authentication successful (alternative method)")
            except Exception as e2:
                # Provide helpful error message
                if '401' in error_msg or 'authenticate' in error_msg.lower():
                    raise Exception(
                        f"Twikit authentication failed (401): Check your credentials. "
                        f"Ensure 2FA is disabled or use an app password. Error: {e2}"
                    )
                else:
                    raise Exception(f"Twikit authentication failed: {e2}")
        
        # Save cookies for future use
        try:
            import aiofiles
            cookies = self.client.get_cookies()
            async with aiofiles.open(self.cookies_file, 'w') as f:
                await f.write(json.dumps(cookies))
            logger.info("Twikit: Saved cookies for future use")
        except Exception as e:
            logger.warning(f"Twikit: Failed to save cookies: {e}")
        
        self._initialized = True
    
    async def _scrape_async(self, username: str, start_date=None, end_date=None, max_tweets=1000):
        """Async scraping method"""
        await self._ensure_authenticated()
        
        tweets = []
        count = 0
        
        try:
            # Get user first
            user = await self.client.get_user_by_screen_name(username)
            
            # Get user tweets - Twikit uses get_user_tweets method
            user_tweets = await user.get_tweets(count=max_tweets)
            
            for tweet in user_tweets:
                # Date filtering
                tweet_date = tweet.created_at
                if isinstance(tweet_date, str):
                    try:
                        tweet_date = datetime.datetime.fromisoformat(tweet_date.replace('Z', '+00:00'))
                    except:
                        tweet_date = datetime.datetime.now(datetime.timezone.utc)
                elif not isinstance(tweet_date, datetime.datetime):
                    tweet_date = datetime.datetime.now(datetime.timezone.utc)
                
                if start_date and tweet_date < start_date:
                    continue
                if end_date and tweet_date > end_date:
                    break
                
                tweets.append({
                    'id': str(tweet.id),
                    'url': f"https://twitter.com/{username}/status/{tweet.id}",
                    'date': tweet_date.isoformat() if hasattr(tweet_date, 'isoformat') else str(tweet_date),
                    'content': getattr(tweet, 'text', None) or getattr(tweet, 'full_text', '') or '',
                    'user': username,
                    'reply_count': getattr(tweet, 'reply_count', 0) or 0,
                    'retweet_count': getattr(tweet, 'retweet_count', 0) or 0,
                    'like_count': getattr(tweet, 'favorite_count', None) or getattr(tweet, 'like_count', 0) or 0,
                    'quote_count': getattr(tweet, 'quote_count', 0) or 0,
                    'is_retweet': getattr(tweet, 'is_retweet', False) or False,
                    'is_reply': bool(getattr(tweet, 'in_reply_to_status_id', None)),
                    'is_quote': bool(getattr(tweet, 'quoted_status_id', None)),
                })
                
                count += 1
                if count >= max_tweets:
                    break
                    
        except Exception as e:
            logger.error(f"Twikit scraping error: {e}")
            raise
        
        return tweets
    
    def scrape_user_tweets(self, username: str, start_date=None, end_date=None, max_tweets=1000):
        """Synchronous wrapper for async scraping"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self._scrape_async(username, start_date, end_date, max_tweets)
        )


class ScraperManager:
    """Manages multiple scrapers with fallback logic"""
    
    def __init__(self):
        self.scrapers = []
        self._initialize_scrapers()
    
    def _initialize_scrapers(self):
        """Initialize all available scrapers in priority order"""
        scraper_classes = [
            TwitterAPIScraper,  # PRIMARY - Official Twitter API v2 (most reliable)
            SnscrapeScraper,    # Fallback 1 - Web scraping
            ScweetScraper,      # Fallback 2 - Alternative scraper
            TweeterPyScraper,   # Fallback 3 - Alternative scraper
            TwikitScraper,      # Fallback 4 - Requires auth
        ]
        
        for scraper_class in scraper_classes:
            try:
                scraper = scraper_class()
                if scraper.is_available():
                    self.scrapers.append(scraper)
                    logger.info(f"Initialized scraper: {scraper.get_name()}")
                else:
                    logger.warning(f"Scraper {scraper.get_name()} is not available")
            except Exception as e:
                logger.warning(f"Failed to initialize scraper {scraper_class.__name__}: {e}")
    
    def get_available_scrapers(self) -> List[str]:
        """Get list of available scraper names"""
        return [s.get_name() for s in self.scrapers]
    
    def scrape_with_fallback(self, username: str, start_date=None, end_date=None, 
                           max_tweets=1000, exclude_retweets=False, 
                           exclude_replies=False, exclude_quotes=False,
                           max_retries=2):
        """Try each scraper in sequence with retry logic until one succeeds"""
        import time
        
        errors = []
        
        for scraper in self.scrapers:
            scraper_name = scraper.get_name()
            
            # Try scraper with retries
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s
                        logger.info(f"Retrying {scraper_name} (attempt {attempt + 1}/{max_retries + 1}) after {wait_time}s")
                        time.sleep(wait_time)
                    
                    logger.info(f"Trying scraper: {scraper_name} (attempt {attempt + 1}/{max_retries + 1})")
                    tweets = scraper.scrape_user_tweets(
                        username, start_date, end_date, max_tweets
                    )
                    
                    if not tweets:
                        error_msg = f"{scraper_name}: No tweets returned"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        if attempt < max_retries:
                            continue  # Retry
                        break  # Move to next scraper
                    
                    # Apply filters
                    filtered_tweets = []
                    for tweet in tweets:
                        if exclude_retweets and tweet.get('is_retweet'):
                            continue
                        if exclude_replies and tweet.get('is_reply'):
                            continue
                        if exclude_quotes and tweet.get('is_quote'):
                            continue
                        filtered_tweets.append(tweet)
                    
                    logger.info(f"Scraper {scraper_name} succeeded with {len(filtered_tweets)} tweets (after {attempt + 1} attempt(s))")
                    return {
                        'success': True,
                        'tweets': filtered_tweets,
                        'scraper_used': scraper_name,
                        'count': len(filtered_tweets),
                        'total_before_filter': len(tweets),
                        'attempts': attempt + 1
                    }
                    
                except Exception as e:
                    error_msg = f"{scraper_name}: {str(e)}"
                    logger.warning(f"Scraper {scraper_name} failed (attempt {attempt + 1}): {error_msg}")
                    
                    # Don't retry on certain errors (auth failures, etc.)
                    if any(keyword in error_msg.lower() for keyword in ['401', 'authenticate', 'credentials', 'not configured']):
                        errors.append(f"{error_msg} (not retrying)")
                        break  # Move to next scraper
                    
                    if attempt < max_retries:
                        errors.append(f"{error_msg} (will retry)")
                        continue  # Retry
                    else:
                        errors.append(error_msg)
                        break  # Move to next scraper
        
        # All scrapers failed
        logger.error(f"All scrapers failed for username: {username} after {max_retries + 1} attempts each")
        return {
            'success': False,
            'error': 'All scrapers failed to retrieve tweets',
            'errors': errors,
            'available_scrapers': self.get_available_scrapers(),
            'attempts_per_scraper': max_retries + 1
        }

