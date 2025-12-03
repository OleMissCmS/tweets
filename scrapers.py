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
            return True
        except ImportError:
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
        """Ensure client is authenticated"""
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
        username = os.getenv('TWITTER_USERNAME')
        email = os.getenv('TWITTER_EMAIL')
        password = os.getenv('TWITTER_PASSWORD')
        
        if not all([username, email, password]):
            raise Exception("Twikit credentials not configured. Set TWITTER_USERNAME, TWITTER_EMAIL, and TWITTER_PASSWORD environment variables.")
        
        logger.info("Twikit: Authenticating with credentials...")
        await self.client.login(
            auth_info_1=username,
            auth_info_2=email,
            password=password
        )
        
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
            SnscrapeScraper,  # Primary - most reliable
            ScweetScraper,    # Alternative 1
            TweeterPyScraper, # Alternative 2
            TwikitScraper,    # Alternative 3 - requires auth
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
                           exclude_replies=False, exclude_quotes=False):
        """Try each scraper in sequence until one succeeds"""
        
        errors = []
        
        for scraper in self.scrapers:
            try:
                logger.info(f"Trying scraper: {scraper.get_name()}")
                tweets = scraper.scrape_user_tweets(
                    username, start_date, end_date, max_tweets
                )
                
                if not tweets:
                    errors.append(f"{scraper.get_name()}: No tweets returned")
                    continue
                
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
                
                logger.info(f"Scraper {scraper.get_name()} succeeded with {len(filtered_tweets)} tweets")
                return {
                    'success': True,
                    'tweets': filtered_tweets,
                    'scraper_used': scraper.get_name(),
                    'count': len(filtered_tweets),
                    'total_before_filter': len(tweets)
                }
                
            except Exception as e:
                error_msg = f"{scraper.get_name()}: {str(e)}"
                errors.append(error_msg)
                logger.warning(f"Scraper {scraper.get_name()} failed: {error_msg}")
                continue
        
        # All scrapers failed
        logger.error(f"All scrapers failed for username: {username}")
        return {
            'success': False,
            'error': 'All scrapers failed to retrieve tweets',
            'errors': errors,
            'available_scrapers': self.get_available_scrapers()
        }

