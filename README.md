# Twitter Tweet Scraper Web App

A web application for scraping tweets by username with date range filtering and content type filtering (retweets, replies, quotes).

## Features

- 🐦 Scrape tweets by username
- 📅 Filter by date range (start and end dates)
- 🔍 Filter out retweets, replies, and quote tweets
- 📥 Download results as JSON or CSV
- 🎨 Modern, responsive UI

## Setup

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open your browser to `http://localhost:5000`

## Deployment on Render

1. Push this repository to GitHub
2. Connect your GitHub repository to Render
3. Create a new Web Service
4. Render will automatically detect the `render.yaml` configuration
5. Deploy!

## Usage

1. Enter a Twitter username (without @)
2. Optionally set a date range
3. Select filtering options (exclude retweets, replies, quotes)
4. Click "Scrape Tweets"
5. Download results as JSON or CSV

## Built With

- [Flask](https://flask.palletsprojects.com/) - Web framework
- [snscrape](https://github.com/JustAnotherArchivist/snscrape) - Twitter scraping library
- HTML/CSS/JavaScript - Frontend

## License

This project uses snscrape, which is licensed under GPL-3.0.
