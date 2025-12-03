let currentTweets = [];

document.getElementById('scrapeForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value.trim().replace('@', '');
    const startDate = document.getElementById('start_date').value;
    const endDate = document.getElementById('end_date').value;
    const excludeRetweets = document.getElementById('exclude_retweets').checked;
    const excludeReplies = document.getElementById('exclude_replies').checked;
    const excludeQuotes = document.getElementById('exclude_quotes').checked;
    
    if (!username) {
        showError('Please enter a username');
        return;
    }
    
    // Hide previous results and errors
    document.getElementById('results').style.display = 'none';
    document.getElementById('error').style.display = 'none';
    
    // Show loading state
    const btn = document.getElementById('scrapeBtn');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    
    btn.disabled = true;
    btnText.textContent = 'Scraping...';
    btnSpinner.style.display = 'inline';
    
    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username,
                start_date: startDate || null,
                end_date: endDate || null,
                exclude_retweets: excludeRetweets,
                exclude_replies: excludeReplies,
                exclude_quotes: excludeQuotes
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'An error occurred');
        }
        
        currentTweets = data.tweets || [];
        const scraperUsed = data.scraper_used || 'unknown';
        displayResults(currentTweets, data.count, data.username, scraperUsed);
        
    } catch (error) {
        let errorMessage = error.message || 'Failed to scrape tweets. Please try again.';
        
        // Handle multi-line error messages from the server
        if (errorMessage.includes('\n')) {
            errorMessage = errorMessage.split('\n').join('<br>');
        }
        
        showError(errorMessage);
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Scrape Tweets';
        btnSpinner.style.display = 'none';
    }
});

function displayResults(tweets, count, username, scraperUsed) {
    document.getElementById('tweetCount').textContent = count;
    const scraperInfo = document.getElementById('scraperInfo');
    if (scraperInfo && scraperUsed) {
        scraperInfo.textContent = `(via ${scraperUsed})`;
    }
    document.getElementById('results').style.display = 'block';
    
    const tweetsList = document.getElementById('tweetsList');
    tweetsList.innerHTML = '';
    
    if (tweets.length === 0) {
        tweetsList.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">No tweets found matching your criteria.</p>';
        return;
    }
    
    tweets.forEach(tweet => {
        const tweetCard = document.createElement('div');
        tweetCard.className = 'tweet-card';
        
        const badges = [];
        if (tweet.is_retweet) badges.push('<span class="badge badge-retweet">Retweet</span>');
        if (tweet.is_reply) badges.push('<span class="badge badge-reply">Reply</span>');
        if (tweet.is_quote) badges.push('<span class="badge badge-quote">Quote</span>');
        
        const date = new Date(tweet.date);
        const formattedDate = date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        tweetCard.innerHTML = `
            <div class="tweet-header">
                <span class="tweet-user">@${tweet.user}</span>
                <span class="tweet-date">${formattedDate}</span>
            </div>
            <div class="tweet-content">${escapeHtml(tweet.content)}</div>
            ${badges.length > 0 ? `<div class="tweet-badges">${badges.join('')}</div>` : ''}
            <div class="tweet-stats">
                <span>❤️ ${tweet.like_count.toLocaleString()}</span>
                <span>🔄 ${tweet.retweet_count.toLocaleString()}</span>
                <span>💬 ${tweet.reply_count.toLocaleString()}</span>
                <span>🔁 ${tweet.quote_count.toLocaleString()}</span>
            </div>
            <div style="margin-top: 10px;">
                <a href="${tweet.url}" target="_blank" style="color: #1da1f2; text-decoration: none; font-size: 0.9em;">View on Twitter →</a>
            </div>
        `;
        
        tweetsList.appendChild(tweetCard);
    });
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    // Support HTML in error messages
    errorDiv.innerHTML = message;
    errorDiv.style.display = 'block';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Download handlers
document.getElementById('downloadJson').addEventListener('click', () => {
    if (currentTweets.length === 0) {
        alert('No tweets to download');
        return;
    }
    
    downloadTweets('json');
});

document.getElementById('downloadCsv').addEventListener('click', () => {
    if (currentTweets.length === 0) {
        alert('No tweets to download');
        return;
    }
    
    downloadTweets('csv');
});

async function downloadTweets(format) {
    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                format: format,
                tweets: currentTweets
            })
        });
        
        if (!response.ok) {
            throw new Error('Download failed');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = response.headers.get('Content-Disposition')?.split('filename=')[1]?.replace(/"/g, '') || `tweets.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        alert('Failed to download tweets: ' + error.message);
    }
}

