# CET-Mentor v2.0: Professional MHT-CET Admissions Assistant

A sophisticated, production-ready chatbot application designed to help students with MHT-CET engineering college admissions. Built with Flask, OpenAI integration via OpenRouter, and a modern dark UI using Tailwind CSS.

## Features

- **Rank-Based College Suggestions**: Input your MHT-CET rank to get personalized college recommendations
- **AI-Powered Chat**: Ask questions about the admissions process and get intelligent responses
- **Real-time Data Scraping**: Scrape college data from Shiksha.com (or use provided sample data)
- **Modern Dark UI**: Professional interface built with Tailwind CSS
- **Streaming Responses**: Real-time AI responses for better user experience
- **RAG (Retrieval-Augmented Generation)**: Context-aware responses based on college database
- **Feedback System**: Built-in user feedback logging for continuous improvement

## Technology Stack

- **Backend**: Python 3.9+, Flask, Flask-Session
- **Frontend**: HTML5, Tailwind CSS, JavaScript (ES6+)
- **Web Scraping**: requests, BeautifulSoup4
- **Data Handling**: pandas
- **AI Integration**: OpenAI library (configured for OpenRouter)
- **Environment Management**: python-dotenv

## Project Structure

```
├── app.py                 # Main Flask application
├── scraper.py            # Web scraper for Shiksha.com
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
├── mht_cet_data.json    # College data (sample included)
├── feedback_log.csv     # User feedback log (created automatically)
└── README.md            # This file
```

## Quick Start

### 1. Clone and Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your actual API keys
```

### 2. Configure Environment Variables

Edit the `.env` file with your credentials:

```env
FLASK_SECRET_KEY="your-strong-secret-key-here"
OPENROUTER_API_KEY="sk-or-v1-your-openrouter-api-key"
```

**Get your OpenRouter API key**: Visit [OpenRouter.ai](https://openrouter.ai) to create an account and get your API key.

### 3. Run the Application

```bash
# Option 1: Use sample data (recommended for testing)
python app.py

# Option 2: Scrape fresh data first (optional)
python scraper.py  # This will create/update mht_cet_data.json
python app.py
```

### 4. Access the Application

Open your browser and navigate to: `http://localhost:5000`

## Usage Guide

### Getting College Suggestions
- Simply type your MHT-CET rank (e.g., `1500`) and press Enter
- The system will automatically detect it's a rank and provide suggestions
- You'll get two categories:
  - **Good Possibilities**: Colleges where your rank meets/exceeds the cutoff
  - **Ambitious Goals**: Colleges that might be slightly out of reach but worth trying

### Asking Questions
- Type any question about MHT-CET admissions
- Examples: "What is the cutoff for VJTI?" or "Tell me about computer science programs"
- The AI will provide contextual answers based on the college database

## API Endpoints

- `GET /` - Main chat interface
- `POST /suggest` - Get college suggestions for a rank
- `POST /chat` - Stream AI chat responses
- `POST /feedback` - Log user feedback

## Data Scraping

The `scraper.py` file is designed to extract college data from Shiksha.com:

```bash
python scraper.py
```

**Features**:
- Handles pagination automatically
- Robust error handling and logging
- Respects server rate limits
- Cleans and deduplicates data
- Saves data in JSON format

## Deployment

For production deployment:

```bash
# Install gunicorn (included in requirements.txt)
gunicorn --bind 0.0.0.0:8000 app:app

# Or with more workers
gunicorn --workers 4 --bind 0.0.0.0:8000 app:app
```

## Architecture Details

### Rank-Based Logic
- **Lower rank = Better performance** (MHT-CET system)
- Safe suggestions: Colleges with cutoff ranks ≥ user's rank
- Ambitious suggestions: Colleges with cutoff ranks slightly < user's rank

### RAG Implementation
- Searches college database for relevant context
- Provides context to AI for accurate, data-driven responses
- Fallback to general knowledge when no specific data found

### Security Features
- Server-side session management
- Environment-based configuration
- Input validation and sanitization
- Rate limiting considerations

## Customization

### Adding New Data Sources
Modify `scraper.py` to add new websites:
1. Add new parsing functions
2. Update the main scraping logic
3. Ensure data format consistency

### UI Customization
The HTML template is embedded in `app.py`. Key areas to customize:
- Color scheme (Tailwind classes)
- Layout structure
- JavaScript functionality

### AI Model Configuration
Change the AI model in `app.py`:
```python
model="anthropic/claude-3.5-sonnet"  # Current model
# model="openai/gpt-4"               # Alternative
```

## Troubleshooting

### Common Issues

1. **"OPENROUTER_API_KEY not found"**
   - Ensure your `.env` file exists and contains the API key
   - Verify the key format starts with `sk-or-v1-`

2. **"College data not available"**
   - Run `python scraper.py` to generate fresh data
   - Or ensure `mht_cet_data.json` exists with valid data

3. **Scraping fails**
   - Website structure may have changed
   - Check internet connection
   - Review scraper logs for specific errors

4. **AI responses not working**
   - Verify OpenRouter API key is valid
   - Check account credits/usage limits
   - Review server logs for API errors

### Debug Mode
Run with debug enabled:
```bash
export FLASK_ENV=development
python app.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open-source. Please ensure you comply with the terms of service of any external APIs or websites used.

## Disclaimer

This application is for educational and informational purposes. Admission decisions should always be verified with official sources. The developers are not responsible for any admission-related decisions made based on this tool's suggestions.