

from flask import Flask, render_template_string, request, jsonify, session, Response
import json
import pandas as pd
import openai
import os
import logging
from datetime importdatetime
import csv
from typing import List, Dict, Any
from dotenv import load_dotenv

# --- Basic Configuration ---
load_dotenv() # Load environment variables from .env file

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Flask App Initialization ---
app = Flask(__name__)
# IMPORTANT: Change this secret key for production environments!
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem" # Server-side sessions

from flask_session import Session
Session(app)


# --- OpenAI Client Configuration (using OpenRouter) ---
# It's highly recommended to set your API key as an environment variable
api_key = os.environ.get("OPENROUTER_API_KEY")
if not api_key:
    # Fallback to a placeholder if the key is not found in environment variables
    api_key = "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" # PASTE YOUR KEY HERE
    logger.warning("OPENROUTER_API_KEY not found in environment. Using placeholder key.")

# This is the modern (v1.x) way to initialize the OpenAI client
try:
    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
except openai.OpenAIError as e:
    logger.critical(f"Failed to initialize OpenAI client: {e}")
    client = None

# Global data storage, managed by the assistant class
df_colleges = pd.DataFrame()

class MHTCETAssistant:
    """
    Encapsulates all the logic for the MHT-CET chatbot.
    """
    def __init__(self):
        self.df_colleges = pd.DataFrame()
        self.load_data()
        self.system_prompt = self.build_system_prompt()

    def load_data(self):
        """Load MHT-CET data from JSON file into a pandas DataFrame."""
        try:
            with open('mht_cet_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Standardize column names during loading
            # This ensures consistency with the scraper's output
            self.df_colleges = pd.DataFrame(data)
            self.df_colleges.rename(columns={
                'college_name': 'college',
                'branch_name': 'branch',
                'closing_percentile': 'cutoff_percentile'
            }, inplace=True, errors='ignore')
            
            # Ensure percentile is a numeric type for calculations
            if 'cutoff_percentile' in self.df_colleges.columns:
                self.df_colleges['cutoff_percentile'] = pd.to_numeric(self.df_colleges['cutoff_percentile'])

            logger.info(f"Successfully loaded {len(self.df_colleges)} college records.")
            return True
        
        except FileNotFoundError:
            logger.error("'mht_cet_data.json' not found! Please run scraper.py first.")
            return False
        except Exception as e:
            logger.error(f"An error occurred while loading data: {e}")
            return False

    def build_system_prompt(self):
        """Builds the master system prompt for the AI assistant."""
        current_year = datetime.now().year
        return f"""You are 'CET-Mentor', an expert AI assistant specializing in MHT-CET admissions for Maharashtra engineering colleges. The current year is {current_year}. All your advice should be relevant for the upcoming admissions.

**CORE DIRECTIVES:**
1.  **Truth Source:** You MUST prioritize the "VERIFIED CONTEXT" provided in this prompt. This data is the absolute source of truth. If it contradicts your general knowledge, you MUST state the verified data as correct and explain that it's based on provided records.
2.  **Data-Driven:** Always provide quantitative answers (ranks, percentiles) when available in the context. Be precise.
3.  **Scope Limitation:** Strictly confine your discussion to MHT-CET system colleges. Politely refuse to discuss IITs, NITs, BITS, JEE, or any other exam system.
4.  **Tone:** Your tone should be professional, encouraging, and supportive, yet realistic. Use clear language and avoid jargon.
5.  **Formatting:** Use markdown (especially bullet points and bold text) to structure your responses for clarity.
6.  **No Context Fallback:** If no VERIFIED CONTEXT is provided, you may use your general knowledge about the MHT-CET process but must explicitly state that the information is general and not based on specific data for the user's query.
"""

    def search_relevant_data(self, query: str, limit: int = 5) -> List[Dict]:
        """Performs a keyword search on the dataframe to find relevant context."""
        if self.df_colleges.empty:
            return []
        
        keywords = [word for word in re.split(r'\s|,|\(|\)', query.lower()) if len(word) > 3]
        if not keywords:
            return []
            
        # Create a boolean mask for rows that match any keyword in either college or branch
        college_mask = self.df_colleges['college'].str.lower().apply(lambda x: any(key in x for key in keywords))
        branch_mask = self.df_colleges['branch'].str.lower().apply(lambda x: any(key in x for key in keywords))
        
        combined_mask = college_mask | branch_mask
        
        # Get the top N matches, sorted by percentile
        relevant_df = self.df_colleges[combined_mask].sort_values(by='cutoff_percentile', ascending=False).head(limit)
        
        return relevant_df.to_dict('records')

    def rank_to_percentile(self, rank: int, total_candidates: int = 350000) -> float:
        """
        Converts MHT-CET rank to an approximate percentile.
        Note: total_candidates is an estimate for the PCM group and varies each year.
        """
        if rank <= 0: return 100.0
        percentile = (1 - (rank / total_candidates)) * 100
        return round(max(0, min(100, percentile)), 4)

    def predict_admission_chance(self, user_percentile: float, cutoff_percentile: float) -> str:
        """Categorizes admission chance based on the percentile difference."""
        difference = user_percentile - cutoff_percentile
        
        if difference >= 2: return "Very High"
        if difference >= 0.5: return "High"
        if difference >= -0.75: return "Medium (Borderline)"
        if difference >= -2.5: return "Low"
        return "Unlikely"

    def suggest_colleges(self, user_rank: int, category: str = "General", limit: int = 7) -> Dict[str, Any]:
        """Suggests best-fit colleges based on user rank with 'Safe' and 'Ambitious' categories."""
        if self.df_colleges.empty:
            return {"safe": [], "ambitious": [], "user_percentile": 0}
            
        user_percentile = self.rank_to_percentile(user_rank)
        
        # For simplicity in this version, we will filter by General category if the specific one is not found.
        # A more advanced version would handle category-specific cutoffs.
        df_filtered = self.df_colleges[self.df_colleges['category'].str.upper() == "GENERAL"].copy()
        
        if df_filtered.empty:
            return {"safe": [], "ambitious": [], "user_percentile": user_percentile}

        # Safe options: Cutoff is lower than the user's percentile
        safe_df = df_filtered[df_filtered['cutoff_percentile'] <= user_percentile]
        safe_suggestions = safe_df.sort_values(by='cutoff_percentile', ascending=False).head(limit)
        
        # Ambitious options: Cutoff is slightly higher than the user's percentile
        ambitious_df = df_filtered[df_filtered['cutoff_percentile'] > user_percentile]
        ambitious_suggestions = ambitious_df.sort_values(by='cutoff_percentile', ascending=True).head(limit)
        
        return {
            "safe": safe_suggestions.to_dict('records'),
            "ambitious": ambitious_suggestions.to_dict('records'),
            "user_percentile": user_percentile
        }

    def generate_response_stream(self, user_message: str, context_data: List[Dict] = None):
        """Generates a streaming AI response using the modern OpenAI client."""
        if not client:
            yield "data: {\"error\": \"AI client not initialized. Check API key.\"}\n\n"
            return

        messages = [{"role": "system", "content": self.system_prompt}]
        
        if context_data:
            context_text = "VERIFIED CONTEXT (Use this as the primary source of truth):\n"
            for item in context_data:
                context_text += f"- College: {item['college']} | Branch: {item['branch']} | Cutoff: {item['cutoff_percentile']:.4f}% | Category: {item['category']}\n"
            messages.append({"role": "system", "content": context_text})
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            stream = client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                messages=messages,
                max_tokens=700,
                temperature=0.5,
                stream=True
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    # SSE format: data: {...}\n\n
                    yield f"data: {json.dumps({'content': content})}\n\n"
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            yield f"data: {json.dumps({'error': 'Sorry, I am having trouble connecting to my brain right now. Please try again later.'})}\n\n"

# --- Global Assistant Instance ---
assistant = MHTCETAssistant()

# --- Flask Routes ---

@app.route('/')
def index():
    """Serves the main chat interface from the INDEX_HTML string."""
    return render_template_string(INDEX_HTML)

@app.route('/suggest', methods=['POST'])
def handle_suggest():
    """API endpoint to get college suggestions."""
    data = request.json
    try:
        rank = int(data.get('rank', 0))
        if rank <= 0:
            return jsonify({'success': False, 'error': 'Please provide a valid rank.'}), 400
            
        suggestions = assistant.suggest_colleges(user_rank=rank)
        
        session['last_suggestion'] = suggestions # Store for conversational context
        
        return jsonify({
            'success': True,
            'rank': rank,
            'percentile': suggestions['user_percentile'],
            'suggestions': suggestions
        })
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid rank format. Please enter a number.'}), 400
    except Exception as e:
        logger.error(f"Error in /suggest endpoint: {e}")
        return jsonify({'success': False, 'error': 'An internal error occurred.'}), 500

@app.route('/predict', methods=['POST'])
def handle_predict():
    """API endpoint to predict admission chances."""
    data = request.json
    try:
        percentile = float(data.get('percentile', 0))
        college_query = data.get('college', '').strip()
        
        if not college_query or percentile <= 0:
            return jsonify({'success': False, 'error': 'Please provide a valid percentile and college name.'}), 400

        # Find the best match for the college query
        match = assistant.df_colleges[assistant.df_colleges['college'].str.contains(college_query, case=False, na=False)]
        
        if match.empty:
            return jsonify({'success': False, 'error': f"Could not find any college matching '{college_query}' in the database."})
        
        # For this version, we take the highest cutoff for the matched college
        cutoff_data = match.sort_values(by='cutoff_percentile', ascending=False).iloc[0]
        
        admission_chance = assistant.predict_admission_chance(percentile, cutoff_data['cutoff_percentile'])
        
        return jsonify({
            'success': True,
            'user_percentile': percentile,
            'college': cutoff_data['college'],
            'branch': cutoff_data['branch'],
            'cutoff_percentile': cutoff_data['cutoff_percentile'],
            'admission_chance': admission_chance
        })
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid percentile. Please enter a number.'}), 400
    except Exception as e:
        logger.error(f"Error in /predict endpoint: {e}")
        return jsonify({'success': False, 'error': 'An internal error occurred.'}), 500


@app.route('/chat', methods=['POST'])
def handle_chat():
    """API endpoint to handle general chat messages with RAG."""
    data = request.json
    user_message = data.get('message', '').strip()
    if not user_message:
        return Response(status=400) # Bad request for empty message
        
    context_data = assistant.search_relevant_data(user_message)
    
    # SSE response
    return Response(assistant.generate_response_stream(user_message, context_data), mimetype='text/event-stream')

@app.route('/feedback', methods=['POST'])
def handle_feedback():
    """API endpoint to log user feedback."""
    try:
        data = request.json
        feedback_file = 'feedback_log.csv'
        file_exists = os.path.isfile(feedback_file)
        
        with open(feedback_file, 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['timestamp', 'type', 'user_message', 'bot_response', 'correction']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'timestamp': datetime.now().isoformat(),
                'type': data.get('type'),
                'user_message': data.get('message'),
                'bot_response': data.get('response'),
                'correction': data.get('correction', '')
            })
        
        logger.info(f"Logged {data.get('type')} feedback.")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error logging feedback: {e}")
        return jsonify({'success': False, 'error': 'Failed to log feedback'}), 500

# --- Frontend HTML/CSS/JS ---
# This contains the complete, functional frontend for the chatbot.
INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CET-Mentor - MHT-CET Admissions Assistant</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #eef2f3;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 800px;
            height: 90vh;
            max-height: 700px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px;
            text-align: center;
            flex-shrink: 0;
        }
        .header h1 { font-size: 22px; margin-bottom: 4px; }
        .header p { opacity: 0.9; font-size: 14px; }
        .messages {
            flex-grow: 1;
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .message { padding: 10px 15px; border-radius: 18px; max-width: 80%; line-height: 1.5; }
        .message.user {
            background: #007bff;
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .message.bot {
            background: #f1f0f0;
            color: #333;
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }
        .message.bot strong { color: #667eea; }
        .message.bot ul { padding-left: 20px; margin-top: 8px; }
        .message.bot li { margin-bottom: 4px; }
        .message.bot .feedback-buttons { margin-top: 10px; border-top: 1px solid #ddd; padding-top: 8px; display: none;}
        .message.bot .feedback-btn { background: none; border: 1px solid #ccc; font-size: 16px; cursor: pointer; margin-right: 5px; padding: 2px 6px; border-radius: 12px; transition: all 0.2s; }
        .message.bot .feedback-btn:hover { background: #ddd; }
        .message.bot .feedback-btn:disabled { cursor: default; opacity: 0.5; }
        .input-area { padding: 15px; background: #fff; border-top: 1px solid #e9ecef; flex-shrink: 0; }
        .input-row { display: flex; gap: 10px; margin-bottom: 10px; }
        #message-input {
            flex: 1;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 25px;
            outline: none;
            font-size: 14px;
            transition: border-color 0.2s;
        }
        #message-input:focus { border-color: #667eea; }
        #send-btn {
             padding: 10px 20px; border: none; border-radius: 20px; cursor: pointer; font-weight: bold; transition: all 0.3s;
             background: #007bff; color: white; font-size: 14px;
        }
        #send-btn:hover { background: #0056b3; }
        .button-row { display: flex; gap: 10px; justify-content: center; }
        .action-btn {
            padding: 10px 20px; border: 1px solid #667eea; border-radius: 20px; cursor: pointer; font-weight: 500;
            transition: all 0.3s; color: #667eea; background: white; font-size: 14px;
        }
        .action-btn:hover { background: #667eea; color: white; }
        .typing-indicator { align-self: flex-start; }
        .typing-indicator span { display: inline-block; width: 8px; height: 8px; margin: 0 1px; background-color: #888; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
        .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
        .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>CET-Mentor</h1>
            <p>Your Personal MHT-CET Admissions Assistant</p>
        </div>
        <div class="messages" id="messages-container">
            <div class="message bot">Hello! How can I assist you with your MHT-CET admissions today? You can ask a question or use one of the buttons below.</div>
        </div>
        <div class="input-area">
            <div class="input-row">
                <input type="text" id="message-input" placeholder="Type your rank for suggestions, or ask a question...">
                <button id="send-btn">Send</button>
            </div>
            <div class="button-row">
                <button class="action-btn" id="suggest-btn">Suggest Colleges</button>
                <button class="action-btn" id="predict-btn">Predict Admission Chance</button>
            </div>
        </div>
    </div>
    <script>
        const messagesContainer = document.getElementById('messages-container');
        const messageInput = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');
        const suggestBtn = document.getElementById('suggest-btn');
        const predictBtn = document.getElementById('predict-btn');
        let messageCounter = 0;

        const addMessage = (text, type, id=null) => {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${type}`;
            msgDiv.innerHTML = text; // Use innerHTML to render markdown from AI
            if (id) msgDiv.id = id;
            messagesContainer.appendChild(msgDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            return msgDiv;
        };
        
        const addTypingIndicator = () => {
            const indicator = document.createElement('div');
            indicator.className = 'message bot typing-indicator';
            indicator.id = 'typing-indicator';
            indicator.innerHTML = '<span></span><span></span><span></span>';
            messagesContainer.appendChild(indicator);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        };

        const removeTypingIndicator = () => {
            const indicator = document.getElementById('typing-indicator');
            if(indicator) indicator.remove();
        };
        
        const handleSend = async () => {
            const userText = messageInput.value.trim();
            if (!userText) return;
            addMessage(userText, 'user');
            messageInput.value = '';

            // Smart Intent: If user types only a number, treat it as a rank for suggestion
            if (/^\\d{1,6}$/.test(userText)) {
                await fetchSuggestions(userText);
            } else {
                await fetchChatResponse(userText);
            }
        };

        const fetchChatResponse = async (message) => {
            addTypingIndicator();
            const botMsgId = `bot-msg-${++messageCounter}`;
            let botMsgDiv = null;
            let fullResponseText = "";
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: message})
                });
                
                removeTypingIndicator();
                botMsgDiv = addMessage("", 'bot', botMsgId);

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                while(true) {
                    const {value, done} = await reader.read();
                    if(done) break;
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\\n');
                    lines.forEach(line => {
                        if (line.startsWith('data: ')) {
                            try {
                                const jsonData = JSON.parse(line.substring(6));
                                if(jsonData.content) {
                                    fullResponseText += jsonData.content;
                                    // Basic markdown rendering
                                    let formattedContent = fullResponseText.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br>');
                                    botMsgDiv.innerHTML = formattedContent;
                                }
                                if(jsonData.error) {
                                    botMsgDiv.innerHTML = `<p style="color:red;">Error: ${jsonData.error}</p>`;
                                }
                            } catch(e) {/* Incomplete JSON, wait for next chunk */}
                        }
                    });
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }
            } catch (e) {
                removeTypingIndicator();
                if(!botMsgDiv) botMsgDiv = addMessage("", 'bot', botMsgId);
                botMsgDiv.innerHTML = "Sorry, something went wrong. Could not connect to the server.";
            } finally {
                if(botMsgDiv) addFeedbackButtons(botMsgDiv, message, fullResponseText);
            }
        };

        const fetchSuggestions = async (rank) => {
            addTypingIndicator();
            try {
                const response = await fetch('/suggest', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({rank: rank})
                });
                const data = await response.json();
                removeTypingIndicator();

                if (data.success) {
                    let html = `Based on your rank of <strong>${data.rank}</strong> (approx. ${data.percentile.toFixed(4)} percentile), here are some suggestions:<br><br>`;
                    if(data.suggestions.safe && data.suggestions.safe.length > 0) {
                        html += '<strong>🎯 Good Possibilities (Cutoff ≤ Your Percentile):</strong><ul>';
                        data.suggestions.safe.forEach(s => {
                            html += `<li><strong>${s.college}</strong><br>(${s.branch}) - Cutoff: ${s.cutoff_percentile}%</li>`;
                        });
                        html += '</ul><br>';
                    }
                    if(data.suggestions.ambitious && data.suggestions.ambitious.length > 0) {
                         html += '<strong> ambitious Goals (Cutoff > Your Percentile):</strong><ul>';
                        data.suggestions.ambitious.forEach(s => {
                            html += `<li><strong>${s.college}</strong><br>(${s.branch}) - Cutoff: ${s.cutoff_percentile}%</li>`;
                        });
                        html += '</ul>';
                    }
                    if (data.suggestions.safe.length === 0 && data.suggestions.ambitious.length === 0) {
                        html += "I couldn't find specific suggestions in the database for your rank. This could be because your rank is very high, or the data doesn't cover this range.";
                    }
                    addMessage(html, 'bot');
                } else {
                    addMessage(`Error: ${data.error}`, 'bot');
                }
            } catch (e) {
                removeTypingIndicator();
                addMessage('Could not fetch suggestions. Please check your connection.', 'bot');
            }
        };
        
        const addFeedbackButtons = (msgDiv, userMessage, botResponse) => {
            const feedbackDiv = document.createElement('div');
            feedbackDiv.className = 'feedback-buttons';
            feedbackDiv.innerHTML = `<button class="feedback-btn" data-type="positive">👍</button><button class="feedback-btn" data-type="negative">👎</button>`;
            msgDiv.appendChild(feedbackDiv);
            feedbackDiv.style.display = 'block';

            feedbackDiv.querySelectorAll('.feedback-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const type = e.target.getAttribute('data-type');
                    let correction = "";
                    if (type === 'negative') {
                        correction = prompt("Sorry about that! What should the correct answer have been?");
                    }
                    
                    await fetch('/feedback', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({type, message: userMessage, response: botResponse, correction})
                    });
                    
                    feedbackDiv.innerHTML = "<em>Thanks for your feedback!</em>";
                });
            });
        };
        
        sendBtn.addEventListener('click', handleSend);
        messageInput.addEventListener('keydown', (e) => { if(e.key === 'Enter') handleSend(); });
        
        suggestBtn.addEventListener('click', () => {
            const rank = prompt("Please enter your MHT-CET Rank:");
            if(rank && /^\\d+$/.test(rank)) {
                addMessage(`Suggest colleges for rank ${rank}`, 'user');
                fetchSuggestions(rank);
            } else if (rank) {
                alert("Please enter a valid number for the rank.");
            }
        });

        predictBtn.addEventListener('click', async () => {
            const percentile = prompt("Please enter your MHT-CET Percentile:");
            if (!percentile || isNaN(parseFloat(percentile))) {
                if (percentile) alert("Please enter a valid percentile.");
                return;
            }
            const college = prompt("Please enter the college name you're interested in:");
            if(college) {
                addMessage(`Predict my admission chance for ${college} with ${percentile}%`, 'user');
                addTypingIndicator();
                 try {
                    const response = await fetch('/predict', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({percentile: percentile, college: college})
                    });
                    const data = await response.json();
                    removeTypingIndicator();
                    let html = "";
                    if (data.success) {
                        html = `For <strong>${data.college}</strong> (${data.branch}), with a previous year cutoff of <strong>${data.cutoff_percentile}%</strong>:<br><br>Your admission chance is: <strong>${data.admission_chance}</strong>`;
                    } else {
                        html = `Error: ${data.error}`;
                    }
                    addMessage(html, 'bot');
                } catch(e) {
                     removeTypingIndicator();
                     addMessage('Could not fetch prediction. Please check your connection.', 'bot');
                }
            }
        });

    </script>
</body>
</html>
"""

if __name__ == '__main__':
    # Note: Use a production WSGI server like Gunicorn or Waitress for deployment.
    # Example: gunicorn --bind 0.0.0.0:8000 app:app
    if client is None:
        logger.critical("Cannot start Flask server: OpenAI client failed to initialize.")
    else:
        app.run(debug=True, port=5000)
