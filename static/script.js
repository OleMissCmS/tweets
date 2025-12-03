let currentTweets = [];
let currentRequestId = null;

// Load queue and rate limit status on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Set default end date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('end_date').value = today;
    document.getElementById('end_date').max = today;
    
    // Set max date for start_date (7 days back for FREE tier)
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const minDate = sevenDaysAgo.toISOString().split('T')[0];
    document.getElementById('start_date').min = minDate;
    document.getElementById('start_date').max = today;
    
    await loadQueue();
    await updateRateLimitStatus();
    // Update rate limit status every 30 seconds
    setInterval(updateRateLimitStatus, 30000);
});

async function loadQueue() {
    try {
        const response = await fetch('/api/queue');
        const data = await response.json();
        
        if (data.queue && data.queue.length > 0) {
            displayQueue(data.queue);
        } else {
            document.getElementById('queueSection').style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading queue:', error);
    }
}

function displayQueue(queue) {
    const queueSection = document.getElementById('queueSection');
    const queueList = document.getElementById('queueList');
    
    queueSection.style.display = 'block';
    queueList.innerHTML = '';
    
    queue.forEach(req => {
        const queueItem = document.createElement('div');
        queueItem.className = 'queue-item';
        
        const statusBadge = req.status === 'pending' ? 
            '<span style="color: #ffc107;">⏳ Pending</span>' :
            req.status === 'in_progress' ?
            '<span style="color: #17a2b8;">🔄 In Progress</span>' :
            req.status === 'completed' ?
            '<span style="color: #28a745;">✅ Completed</span>' :
            '<span style="color: #dc3545;">❌ Failed</span>';
        
        queueItem.innerHTML = `
            <div class="queue-item-info">
                <div class="queue-item-username">@${req.username}</div>
                <div class="queue-item-details">
                    ${req.start_date ? `From: ${req.start_date}` : ''} 
                    ${req.end_date ? `To: ${req.end_date}` : ''}
                    | Progress: ${req.progress} tweets
                    | ${statusBadge}
                </div>
            </div>
            <div class="queue-item-actions">
                ${req.status === 'pending' ? 
                    `<button class="btn btn-success btn-small" onclick="resumeRequest('${req.id}')">Resume</button>` : 
                    ''}
                ${req.status === 'completed' ? 
                    `<button class="btn btn-success btn-small" onclick="viewResults('${req.id}')">View Results</button>` : 
                    ''}
                <button class="btn btn-danger btn-small" onclick="deleteRequest('${req.id}')">Delete</button>
            </div>
        `;
        
        queueList.appendChild(queueItem);
    });
}

async function updateRateLimitStatus() {
    try {
        const response = await fetch('/api/rate-limit-status');
        const status = await response.json();
        
        const statusDiv = document.getElementById('rateLimitStatus');
        const statusText = document.getElementById('rateLimitText');
        const waitText = document.getElementById('rateLimitWait');
        
        if (status.can_make_request) {
            statusDiv.style.display = 'block';
            statusDiv.style.background = '#d4edda';
            statusDiv.style.borderColor = '#28a745';
            statusText.textContent = `✅ Rate Limit: ${status.current_requests}/${status.limit} requests available`;
            waitText.textContent = '';
        } else {
            statusDiv.style.display = 'block';
            statusDiv.style.background = '#fff3cd';
            statusDiv.style.borderColor = '#ffc107';
            statusText.textContent = `⏳ Rate Limit: ${status.current_requests}/${status.limit} requests used`;
            waitText.textContent = `Wait: ${status.wait_time_formatted || 'calculating...'}`;
        }
    } catch (error) {
        console.error('Error updating rate limit status:', error);
    }
}

async function resumeRequest(requestId) {
    const btn = document.getElementById('scrapeBtn');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    
    btn.disabled = true;
    btnText.textContent = 'Resuming...';
    btnSpinner.style.display = 'inline';
    
    try {
        const response = await fetch(`/api/queue/${requestId}/resume`, {
            method: 'POST'
        });
        
        const text = await response.text();
        if (!text || text.trim() === '') {
            throw new Error('Server returned empty response');
        }
        const data = JSON.parse(text);
        
        if (data.queued) {
            showError(`Request is still queued. ${data.message}`);
            await loadQueue();
            await updateRateLimitStatus();
        } else if (data.completed) {
            currentTweets = data.tweets || [];
            displayResults(currentTweets, data.count, data.username, data.scraper_used);
            await loadQueue();
            await updateRateLimitStatus();
        } else if (data.in_progress) {
            currentTweets = data.tweets || [];
            currentRequestId = requestId;
            displayResults(currentTweets, data.count, data.username, data.scraper_used);
            showError(`Request in progress: ${data.progress} tweets collected. You can resume again later.`);
            await loadQueue();
            await updateRateLimitStatus();
        } else {
            currentTweets = data.tweets || [];
            displayResults(currentTweets, data.count, data.username, data.scraper_used);
            await loadQueue();
            await updateRateLimitStatus();
        }
    } catch (error) {
        showError('Failed to resume request: ' + error.message);
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Scrape Tweets';
        btnSpinner.style.display = 'none';
    }
}

async function deleteRequest(requestId) {
    if (!confirm('Are you sure you want to delete this request?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/queue/${requestId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            await loadQueue();
        } else {
            const data = await response.json();
            showError(data.error || 'Failed to delete request');
        }
    } catch (error) {
        showError('Failed to delete request: ' + error.message);
    }
}

async function viewResults(requestId) {
    // This would need to fetch results from the queue
    // For now, just show a message
    alert('Viewing results for completed request. Results should be displayed when you resume.');
}

document.getElementById('scrapeForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value.trim().replace('@', '');
    const startDate = document.getElementById('start_date').value;
    const endDate = document.getElementById('end_date').value;
    const excludeRetweets = document.getElementById('exclude_retweets').checked;
    const excludeReplies = document.getElementById('exclude_replies').checked;
    const excludeQuotes = document.getElementById('exclude_quotes').checked;
    const maxTweets = parseInt(document.getElementById('max_tweets').value) || 1000;
    
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
                exclude_quotes: excludeQuotes,
                max_tweets: maxTweets
            })
        });
        
        // Handle JSON parsing with error checking
        let data;
        try {
            const text = await response.text();
            if (!text || text.trim() === '') {
                throw new Error('Server returned empty response');
            }
            data = JSON.parse(text);
        } catch (parseError) {
            throw new Error(`Server error: ${parseError.message}. Response may be empty or invalid.`);
        }
        
        if (response.status === 202) {
            // Request queued
            showError(`Request queued: ${data.message || 'Rate limit reached'}`);
            await loadQueue();
            await updateRateLimitStatus();
        } else if (!response.ok) {
            throw new Error(data.error || 'An error occurred');
        } else {
            // Success
            currentTweets = data.tweets || [];
            const scraperUsed = data.scraper_used || 'unknown';
            displayResults(currentTweets, data.count, data.username, scraperUsed);
            await updateRateLimitStatus();
        }
        
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
                <a href="${tweet.url}" target="_blank" style="color: #C41230; text-decoration: none; font-size: 0.9em;">View on Twitter →</a>
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
