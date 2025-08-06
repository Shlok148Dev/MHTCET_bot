# MHT-CET Admissions Chatbot 🤖

This is a sophisticated, multi-featured chatbot application designed to assist students with the MHT-CET admissions process. It leverages a Flask backend, a Retrieval-Augmented Generation (RAG) architecture with OpenAI models, and a web-scraped knowledge base to provide accurate, data-driven answers.

![Chatbot Screenshot](https://user-images.githubusercontent.com/your-image-url-here.png) 
*(Suggestion: Take a screenshot of your running app and upload it to the web to replace the URL above)*

## ✨ Features

* **College Suggester:** Recommends the best-fit colleges based on a student's MHT-CET rank.
* **Admission Predictor:** Predicts the probability of admission ("Very High," "High," "Medium," "Low," "Unlikely") for a specific college based on percentile.
* **RAG-Powered Chat:** Answers general queries about the admission process. It uses a "Double Approval" system where it first retrieves verified data from its knowledge base and then uses an LLM to generate a natural language response, ensuring answers are grounded in facts.
* **Conversational Memory:** Remembers the context of recent suggestions for natural follow-up questions.
* **Human-in-the-Loop:** A feedback mechanism (👍/👎) logs user interactions to a `feedback_log.csv` for future model improvement.
* **Self-Updating Knowledge Base:** Includes a Python web scraper (`scraper.py`) to build and update the college cutoff database.

## 🛠️ Technology Stack

* **Backend:** Python, Flask, Flask-Session
* **Frontend:** HTML, CSS, JavaScript (with Server-Sent Events for streaming)
* **AI Model:** OpenAI API (configured for OpenRouter)
* **Web Scraping:** `requests`, `BeautifulSoup4`
* **Data Handling:** `pandas`

## 🚀 Getting Started

Follow these steps to run the application locally.

### 1. Prerequisites

* Python 3.8+
* Git

### 2. Clone the Repository

```bash
git clone [https://github.com/your-username/MHT-CET-Chatbot.git](https://github.com/your-username/MHT-CET-Chatbot.git)
cd MHT-CET-Chatbot
```

### 3. Set Up a Virtual Environment

It's highly recommended to use a virtual environment.

```bash
# For Windows
python -m venv venv
venv\Scripts\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Set Up Your API Key

You need an API key from [OpenRouter.ai](https://openrouter.ai) (which is free).

1.  Create a file named `.env` in the project's root directory.
2.  Add your API key to this file:
    ```
    OPENROUTER_API_KEY="sk-or-v1-..."
    ```

### 6. Build the Knowledge Base

Run the scraper to create the `mht_cet_data.json` file.
```bash
python scraper.py
```
*Note: If the scraper fails, the target website's layout may have changed. You may need to update the selectors in `scraper.py`.*

### 7. Run the Application

```bash
flask run
```
The application will be available at `http://127.0.0.1:5000`.

For a production environment, use a WSGI server like Gunicorn:
```bash
gunicorn --bind 0.0.0.0:8000 app:app
```
