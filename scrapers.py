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
    """Twitter API v2 implementation using official API - PRIMARY METHOD"""
    
    def get_name(self) -> str:
        return "Twitter API v2"
    
    def is_available(self) -> bool:
        try:
            import tweepy
            bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
            return bool(bearer_token and bearer_token.strip())
        except ImportError:
            return False
    
    def scrape_user_tweets(self, username: str, start_date=None, end_date=None, max_tweets=1000):
        import tweepy
        
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN', '').strip()
        if not bearer_token:
            raise Exception("TWITTER_BEARER_TOKEN not configured")
        
        # Initialize Twitter API v2 client
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)
        
        try:
            # Get user ID from username
            user = client.get_user(username=username)
            if not user.data:
                raise Exception(f"User '{username}' not found")
            user_id = user.data.id
            
            tweets = []
            next_token = None
            tweet_count = 0
            
            # Build query with exclusions if needed
            # Note: Twitter API v2 has different filtering capabilities
            tweet_fields = [
                'created_at', 'public_metrics', 'author_id', 'conversation_id',
                'in_reply_to_user_id', 'referenced_tweets'
            ]
            
            # Paginate through tweets
            while tweet_count < max_tweets:
                try:
                    # Calculate how many tweets to fetch in this batch
                    max_results = min(100, max_tweets - tweet_count)  # API max is 100 per request
                    
                    # Get user's tweets
                    response = client.get_users_tweets(
                        id=user_id,
                        max_results=max_results,
                        pagination_token=next_token,
                        tweet_fields=tweet_fields,
                        exclude=['retweets'] if start_date is None and end_date is None else None,  # Can exclude retweets at API level
                    )
                    
                    if not response.data:
                        break  # No more tweets
                    
                    for tweet in response.data:
                        # Date filtering
                        tweet_date = tweet.created_at
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
                            # Set flag to break outer loop
                            next_token = None
                            break
                        
                        # Determine tweet type
                        is_retweet = False
                        is_reply = False
                        is_quote = False
                        
                        if hasattr(tweet, 'referenced_tweets') and tweet.referenced_tweets:
                            for ref in tweet.referenced_tweets:
                                if ref.type == 'retweeted':
                                    is_retweet = True
                                elif ref.type == 'quoted':
                                    is_quote = True
                        
                        if hasattr(tweet, 'in_reply_to_user_id') and tweet.in_reply_to_user_id:
                            is_reply = True
                        
                        # Get metrics
                        metrics = tweet.public_metrics if hasattr(tweet, 'public_metrics') else {}
                        
                        tweets.append({
                            'id': str(tweet.id),
                            'url': f"https://twitter.com/{username}/status/{tweet.id}",
                            'date': tweet_date.isoformat(),
                            'content': tweet.text or '',
                            'user': username,
                            'reply_count': metrics.get('reply_count', 0),
                            'retweet_count': metrics.get('retweet_count', 0),
                            'like_count': metrics.get('like_count', 0),
                            'quote_count': metrics.get('quote_count', 0),
                            'is_retweet': is_retweet,
                            'is_reply': is_reply,
                            'is_quote': is_quote,
                        })
                        
                        tweet_count += 1
                        if tweet_count >= max_tweets:
                            break
                    
                    # Check for next page (only if we didn't hit date limit)
                    if next_token is None:
                        break  # Hit date limit or no more tweets
                    
                    if hasattr(response, 'meta') and response.meta and 'next_token' in response.meta:
                        next_token = response.meta['next_token']
                    else:
                        break  # No more pages
                        
                except tweepy.TooManyRequests:
                    logger.warning("Twitter API: Rate limit hit, waiting...")
                    # wait_on_rate_limit=True should handle this, but just in case
                    raise Exception("Rate limit exceeded. Please try again later.")
                except tweepy.Unauthorized:
                    raise Exception("Twitter API authentication failed. Check TWITTER_BEARER_TOKEN.")
                except tweepy.NotFound:
                    raise Exception(f"User '{username}' not found or account is private.")
                except Exception as e:
                    logger.error(f"Twitter API error: {e}")
                    raise
            
            return tweets
            
        except tweepy.Unauthorized as e:
            raise Exception(f"Twitter API authentication failed: {e}. Check your Bearer Token.")
        except tweepy.NotFound as e:
            raise Exception(f"User '{username}' not found: {e}")
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

