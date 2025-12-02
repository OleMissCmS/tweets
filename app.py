from flask import Flask, render_template, request, jsonify, send_file
from snscrape.modules.twitter import TwitterUserScraper
import datetime
import json
import csv
import io
from functools import wraps
import time

app = Flask(__name__)

def handle_rate_limit(func):
    """Decorator to handle rate limiting and errors gracefully"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return wrapper

@app.route('/')
def index():
    """Main page with the form"""
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
@handle_rate_limit
def scrape_tweets():
    """API endpoint to scrape tweets"""
    data = request.json
    
    username = data.get('username', '').strip().lstrip('@')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    exclude_retweets = data.get('exclude_retweets', False)
    exclude_replies = data.get('exclude_replies', False)
    exclude_quotes = data.get('exclude_quotes', False)
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    # Parse dates
    start_datetime = None
    end_datetime = None
    
    if start_date:
        try:
            start_datetime = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            start_datetime = start_datetime.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            return jsonify({'error': 'Invalid start date format. Use YYYY-MM-DD'}), 400
    
    if end_date:
        try:
            end_datetime = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            # Set to end of day
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59, tzinfo=datetime.timezone.utc)
        except ValueError:
            return jsonify({'error': 'Invalid end date format. Use YYYY-MM-DD'}), 400
    
    # Validate date range
    if start_datetime and end_datetime and start_datetime > end_datetime:
        return jsonify({'error': 'Start date must be before end date'}), 400
    
    # Scrape tweets
    tweets = []
    try:
        scraper = TwitterUserScraper(username)
        count = 0
        max_tweets = 10000  # Safety limit
        
        for tweet in scraper.get_items():
            # Date filtering
            if start_datetime and tweet.date < start_datetime:
                continue
            if end_datetime and tweet.date > end_datetime:
                break
            
            # Type filtering
            if exclude_retweets and tweet.retweetedTweet is not None:
                continue
            if exclude_replies and tweet.inReplyToTweetId is not None:
                continue
            if exclude_quotes and tweet.quotedTweet is not None:
                continue
            
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
            
            # Small delay to avoid rate limiting
            if count % 50 == 0:
                time.sleep(0.5)
    
    except Exception as e:
        return jsonify({'error': f'Error scraping tweets: {str(e)}'}), 500
    
    return jsonify({
        'tweets': tweets,
        'count': len(tweets),
        'username': username
    })

@app.route('/api/download', methods=['POST'])
@handle_rate_limit
def download_tweets():
    """Download tweets as CSV or JSON"""
    data = request.json
    format_type = data.get('format', 'json').lower()
    tweets = data.get('tweets', [])
    
    if not tweets:
        return jsonify({'error': 'No tweets to download'}), 400
    
    if format_type == 'csv':
        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'url', 'date', 'content', 'user', 'reply_count', 
            'retweet_count', 'like_count', 'quote_count', 'is_retweet', 
            'is_reply', 'is_quote'
        ])
        writer.writeheader()
        for tweet in tweets:
            writer.writerow(tweet)
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'tweets_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    else:  # JSON
        output = io.BytesIO()
        json_data = json.dumps(tweets, indent=2, ensure_ascii=False)
        output.write(json_data.encode('utf-8'))
        output.seek(0)
        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'tweets_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
