from flask import Flask, render_template, request, jsonify, send_file
import datetime
import json
import csv
import io
import os
from functools import wraps
import logging
from scrapers import ScraperManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize scraper manager once at startup
scraper_manager = ScraperManager()
logger.info(f"Initialized scrapers: {', '.join(scraper_manager.get_available_scrapers())}")

def handle_rate_limit(func):
    """Decorator to handle rate limiting and errors gracefully"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            # Check for specific error types
            if '429' in error_msg or 'rate limit' in error_msg.lower():
                return jsonify({
                    'error': 'Rate limit exceeded. Please wait a few minutes and try again.'
                }), 429
            return jsonify({'error': error_msg}), 500
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
    
    # Use scraper manager with fallback
    max_tweets = 10000  # Safety limit
    
    result = scraper_manager.scrape_with_fallback(
        username=username,
        start_date=start_datetime,
        end_date=end_datetime,
        max_tweets=max_tweets,
        exclude_retweets=exclude_retweets,
        exclude_replies=exclude_replies,
        exclude_quotes=exclude_quotes
    )
    
    if result['success']:
        return jsonify({
            'tweets': result['tweets'],
            'count': result['count'],
            'username': username,
            'scraper_used': result['scraper_used'],
            'total_before_filter': result.get('total_before_filter', result['count'])
        })
    else:
        # All scrapers failed - provide helpful error message
        error_details = result.get('errors', [])
        available_scrapers = result.get('available_scrapers', [])
        
        error_message = 'All scrapers failed to retrieve tweets.\n\n'
        error_message += f'Tried {len(available_scrapers)} scraper(s): {", ".join(available_scrapers)}\n'
        error_message += f'Total attempts: {len(error_details)} (with retries)\n\n'
        error_message += 'Possible reasons:\n'
        error_message += '- Twitter is blocking automated requests\n'
        error_message += '- The account may be private or suspended\n'
        error_message += '- Rate limiting from Twitter\n'
        error_message += '- Network connectivity issues\n'
        error_message += '- Authentication issues (for Twikit)\n\n'
        error_message += 'Please try again in a few minutes or try a different username.'
        error_message += '\n\nTip: Visit /api/test-twikit to test Twikit authentication.'
        
        if error_details:
            error_message += '\n\nTechnical details:\n' + '\n'.join(error_details[:5])  # Show first 5 errors
        
        return jsonify({
            'error': error_message,
            'errors': error_details,
            'available_scrapers': available_scrapers
        }), 500

@app.route('/callback')
def oauth_callback():
    """OAuth 2.0 callback handler - required by X but not actively used for read-only scraping"""
    # For read-only scraping with Bearer Token, this isn't actively used
    # But X requires it to be configured, so we provide a simple handler
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return jsonify({
            'error': f'OAuth error: {error}',
            'message': 'OAuth callback received an error. For read-only scraping, Bearer Token is used instead.'
        }), 400
    
    if code:
        # If you implement OAuth 2.0 PKCE flow in the future, handle the code here
        return jsonify({
            'message': 'OAuth callback received. For read-only scraping, Bearer Token authentication is used.',
            'note': 'This endpoint is configured but not actively used for current read-only operations.',
            'code': code[:10] + '...' if code else None  # Show partial code for debugging (don't expose full code)
        })
    
    return jsonify({
        'message': 'OAuth callback endpoint is configured and ready.',
        'status': 'ok',
        'note': 'This endpoint is required by X Developer Portal configuration but is not actively used for read-only scraping operations.'
    })

@app.route('/api/test-twikit', methods=['GET'])
def test_twikit():
    """Test Twikit authentication - useful for debugging credentials"""
    try:
        from scrapers import TwikitScraper
        import asyncio
        
        scraper = TwikitScraper()
        
        if not scraper.is_available():
            return jsonify({
                'status': 'error',
                'message': 'Twikit not available - check that credentials are set in environment variables',
                'credentials_check': {
                    'TWITTER_USERNAME': bool(os.getenv('TWITTER_USERNAME')),
                    'TWITTER_EMAIL': bool(os.getenv('TWITTER_EMAIL')),
                    'TWITTER_PASSWORD': bool(os.getenv('TWITTER_PASSWORD'))
                }
            }), 400
        
        # Try to authenticate
        async def test_auth():
            await scraper._ensure_authenticated()
            # Test by getting a user
            test_user = await scraper.client.get_user_by_screen_name('twitter')
            return {
                'username': test_user.screen_name,
                'name': test_user.name
            }
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            test_user = loop.run_until_complete(test_auth())
            
            return jsonify({
                'status': 'success',
                'message': 'Twikit authentication successful',
                'test_user': test_user
            })
        except Exception as e:
            error_msg = str(e)
            return jsonify({
                'status': 'error',
                'message': f'Twikit authentication failed: {error_msg}',
                'hints': [
                    'Check that TWITTER_USERNAME, TWITTER_EMAIL, and TWITTER_PASSWORD are correct',
                    'Ensure 2FA is disabled or use an app password',
                    'Verify your account is not locked or suspended',
                    'Check Render logs for more detailed error information'
                ]
            }), 500
            
    except ImportError:
        return jsonify({
            'status': 'error',
            'message': 'Twikit library not installed'
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Unexpected error: {str(e)}'
        }), 500

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
