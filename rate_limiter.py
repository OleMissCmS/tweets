"""
Rate limit tracker for Twitter API v2
Tracks requests per 15-minute window and manages rate limit availability
"""
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Rate limits per tier (requests per 15 minutes)
RATE_LIMITS = {
    'FREE': {
        'per_user': 1,
        'per_app': 1
    },
    'BASIC': {
        'per_user': 5,
        'per_app': 10
    },
    'PRO': {
        'per_user': 900,
        'per_app': 1500
    }
}

RATE_LIMIT_FILE = 'rate_limits.json'
WINDOW_SECONDS = 15 * 60  # 15 minutes


class RateLimiter:
    """Manages rate limit tracking and availability checking"""
    
    def __init__(self, tier: str = 'FREE'):
        """
        Initialize rate limiter
        
        Args:
            tier: API tier ('FREE', 'BASIC', or 'PRO')
        """
        self.tier = tier.upper()
        self.limits = RATE_LIMITS.get(self.tier, RATE_LIMITS['FREE'])
        self.data_file = RATE_LIMIT_FILE
        self._load_data()
    
    def _load_data(self):
        """Load rate limit data from file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.requests = data.get('requests', [])
                    # Update tier if changed
                    if 'tier' in data:
                        self.tier = data['tier'].upper()
                        self.limits = RATE_LIMITS.get(self.tier, RATE_LIMITS['FREE'])
            except Exception as e:
                logger.error(f"Error loading rate limit data: {e}")
                self.requests = []
        else:
            self.requests = []
    
    def _save_data(self):
        """Save rate limit data to file"""
        try:
            data = {
                'tier': self.tier,
                'requests': self.requests,
                'last_updated': datetime.utcnow().isoformat()
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving rate limit data: {e}")
    
    def _clean_old_requests(self):
        """Remove requests older than 15 minutes"""
        now = time.time()
        cutoff = now - WINDOW_SECONDS
        self.requests = [req_time for req_time in self.requests if req_time > cutoff]
    
    def can_make_request(self, use_app_limit: bool = True) -> tuple[bool, Optional[float]]:
        """
        Check if a request can be made
        
        Args:
            use_app_limit: If True, use per_app limit; if False, use per_user limit
        
        Returns:
            Tuple of (can_make_request, seconds_until_available)
        """
        self._clean_old_requests()
        
        limit = self.limits['per_app'] if use_app_limit else self.limits['per_user']
        current_count = len(self.requests)
        
        if current_count < limit:
            return True, None
        
        # Calculate when next request can be made
        oldest_request = min(self.requests)
        next_available = oldest_request + WINDOW_SECONDS
        wait_time = max(0, next_available - time.time())
        
        return False, wait_time
    
    def record_request(self):
        """Record that a request was made"""
        self._clean_old_requests()
        self.requests.append(time.time())
        self._save_data()
        logger.info(f"Recorded request. Current count: {len(self.requests)}/{self.limits['per_app']}")
    
    def get_status(self) -> Dict:
        """Get current rate limit status"""
        self._clean_old_requests()
        
        can_make, wait_time = self.can_make_request()
        
        return {
            'tier': self.tier,
            'current_requests': len(self.requests),
            'limit': self.limits['per_app'],
            'can_make_request': can_make,
            'wait_time_seconds': wait_time,
            'wait_time_formatted': self._format_wait_time(wait_time) if wait_time else None,
            'window_seconds': WINDOW_SECONDS
        }
    
    def _format_wait_time(self, seconds: float) -> str:
        """Format wait time as human-readable string"""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def set_tier(self, tier: str):
        """Update the API tier"""
        self.tier = tier.upper()
        self.limits = RATE_LIMITS.get(self.tier, RATE_LIMITS['FREE'])
        self._save_data()
        logger.info(f"Updated tier to {self.tier}")

