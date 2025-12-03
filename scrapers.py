"""
Multi-scraper abstraction layer with fallback mechanism
Supports multiple Twitter scraping libraries with automatic failover
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import datetime
import logging

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
    """TweeterPy implementation - alternative scraper"""
    
    def get_name(self) -> str:
        return "TweeterPy"
    
    def is_available(self) -> bool:
        try:
            from tweeterpy import TweeterPy
            return True
        except ImportError:
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
    """Twikit implementation - alternative scraper"""
    
    def get_name(self) -> str:
        return "Twikit"
    
    def is_available(self) -> bool:
        try:
            import twikit
            return True
        except ImportError:
            return False
    
    def scrape_user_tweets(self, username: str, start_date=None, end_date=None, max_tweets=1000):
        # Twikit requires authentication, so this is a placeholder
        # You'd need to implement actual Twikit scraping logic with auth
        raise NotImplementedError("Twikit requires authentication setup")


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
            # TwikitScraper,  # Requires auth - commented out for now
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

