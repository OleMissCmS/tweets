"""
Request queue manager for handling rate-limited requests
Manages queued scraping requests with pagination state
"""
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

QUEUE_FILE = 'request_queue.json'


class QueueManager:
    """Manages request queue with pagination state"""
    
    def __init__(self):
        self.queue_file = QUEUE_FILE
        self.queue = []
        self._load_queue()
    
    def _load_queue(self):
        """Load queue from file"""
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)
                    self.queue = data.get('queue', [])
            except Exception as e:
                logger.error(f"Error loading queue: {e}")
                self.queue = []
        else:
            self.queue = []
    
    def _save_queue(self):
        """Save queue to file"""
        try:
            data = {
                'queue': self.queue,
                'last_updated': datetime.utcnow().isoformat()
            }
            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving queue: {e}")
    
    def add_request(self, username: str, start_date: Optional[str] = None,
                   end_date: Optional[str] = None, max_tweets: int = 1000,
                   exclude_retweets: bool = False, exclude_replies: bool = False,
                   exclude_quotes: bool = False) -> str:
        """
        Add a new request to the queue
        
        Returns:
            Request ID (UUID)
        """
        request_id = str(uuid.uuid4())
        
        request = {
            'id': request_id,
            'username': username,
            'start_date': start_date,
            'end_date': end_date,
            'max_tweets': max_tweets,
            'filters': {
                'exclude_retweets': exclude_retweets,
                'exclude_replies': exclude_replies,
                'exclude_quotes': exclude_quotes
            },
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'pagination': {
                'collected_tweets': 0,
                'last_tweet_id': None,
                'next_token': None,
                'total_requested': max_tweets
            },
            'results': []
        }
        
        self.queue.append(request)
        self._save_queue()
        logger.info(f"Added request {request_id} to queue for user {username}")
        
        return request_id
    
    def get_request(self, request_id: str) -> Optional[Dict]:
        """Get a request by ID"""
        for req in self.queue:
            if req['id'] == request_id:
                return req
        return None
    
    def get_pending_requests(self) -> List[Dict]:
        """Get all pending requests"""
        return [req for req in self.queue if req['status'] == 'pending']
    
    def get_all_requests(self) -> List[Dict]:
        """Get all requests (for display)"""
        return self.queue
    
    def update_request_status(self, request_id: str, status: str):
        """Update request status"""
        request = self.get_request(request_id)
        if request:
            request['status'] = status
            request['updated_at'] = datetime.utcnow().isoformat()
            self._save_queue()
    
    def update_pagination(self, request_id: str, collected_tweets: int,
                         last_tweet_id: Optional[str] = None,
                         next_token: Optional[str] = None):
        """Update pagination state for a request"""
        request = self.get_request(request_id)
        if request:
            request['pagination']['collected_tweets'] = collected_tweets
            if last_tweet_id:
                request['pagination']['last_tweet_id'] = last_tweet_id
            if next_token:
                request['pagination']['next_token'] = next_token
            request['updated_at'] = datetime.utcnow().isoformat()
            self._save_queue()
    
    def add_results(self, request_id: str, tweets: List[Dict]):
        """Add tweets to request results"""
        request = self.get_request(request_id)
        if request:
            request['results'].extend(tweets)
            request['updated_at'] = datetime.utcnow().isoformat()
            self._save_queue()
    
    def get_results(self, request_id: str) -> List[Dict]:
        """Get all results for a request"""
        request = self.get_request(request_id)
        if request:
            return request['results']
        return []
    
    def delete_request(self, request_id: str) -> bool:
        """Delete a request from the queue"""
        request = self.get_request(request_id)
        if request:
            self.queue.remove(request)
            self._save_queue()
            logger.info(f"Deleted request {request_id}")
            return True
        return False
    
    def clear_completed(self):
        """Clear completed requests older than 24 hours"""
        cutoff = datetime.utcnow().timestamp() - (24 * 60 * 60)
        original_count = len(self.queue)
        
        self.queue = [
            req for req in self.queue
            if req['status'] != 'completed' or 
            datetime.fromisoformat(req['updated_at']).timestamp() > cutoff
        ]
        
        if len(self.queue) < original_count:
            self._save_queue()
            logger.info(f"Cleared {original_count - len(self.queue)} old completed requests")

