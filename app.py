

import os
import json
import pandas as pd
import openai
import csv
import logging
from flask import Flask, Response, request, jsonify, render_template_string
from flask_session import Session
from dotenv import load_dotenv
from datetime import datetime

# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- App Initialization ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "a-strong-default-secret-key")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# --- OpenAI Client ---
try:
    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )
except TypeError:
    logging.critical("OPENROUTER_API_KEY not found. Please set it in your .env file.")
    client = None

# --- Data Loading ---
try:
    df = pd.read_json("mht_cet_data.json")
    logging.info(f"Successfully loaded {len(df)} records from mht_cet_data.json")
except FileNotFoundError:
    logging.error("mht_cet_data.json not found. Please run scraper.py first.")
    df = pd.DataFrame(columns=['college', 'branch', 'closing_rank'])

# --- Core Logic ---
def get_system_prompt():
    return """You are 'CET-Mentor', an expert AI assistant for MHT-CET engineering admissions. Your primary function is to provide accurate, data-driven advice based on student ranks.

    **Core Directives:**
    1.  **Prioritize VERIFIED CONTEXT:** If context with college data is provided, you MUST use it as the source of truth. All your claims about cutoffs must come from this data.
    2.  **Rank-Based Advice:** All advice must be centered around MHT-CET **ranks**. A lower rank is better. Explain this concept if necessary.
    3.  **Strict Scope:** Do not discuss IITs, NITs, JEE, or other exam systems. Politely decline and refocus the conversation on MHT-CET colleges.
    4.  **Professional Tone:** Be encouraging, realistic, and clear. Use markdown for readability.
    """

# --- Flask Routes ---
@app.route('/')
def index():
    # Renders the frontend from a string variable
    return render_template_string(INDEX_HTML)

@app.route('/suggest', methods=['POST'])
def suggest_colleges_route():
    user_rank = request.json.get('rank')
    if not user_rank or not isinstance(user_rank, int) or user_rank <= 0:
        return jsonify({"error": "Please provide a valid rank."}), 400

    if df.empty:
        return jsonify({"error": "College data not available. Please run the scraper."}), 500

    # A lower rank is better. Find colleges with a closing rank higher than the user's.
    safe_options = df[df['closing_rank'] >= user_rank].sort_values(by='closing_rank', ascending=True).head(7)
    # Ambitious options are those with a closing rank slightly lower (better) than the user's.
    ambitious_options = df[(df['closing_rank'] < user_rank) & (df['closing_rank'] >= user_rank - 5000)].sort_values(by='closing_rank', ascending=False).head(7)

    return jsonify({
        "safe_options": safe_options.to_dict('records'),
        "ambitious_options": ambitious_options.to_dict('records')
    })

@app.route('/chat', methods=['POST'])
def chat_route():
    if not client:
        return Response("AI client not configured.", status=503)

    user_message = request.json.get('message')
    if not user_message:
        return Response("Empty message.", status=400)

    # RAG: Retrieval Step
    context_df = df[df['college'].str.contains(user_message, case=False, na=False)]
    context_str = ""
    if not context_df.empty:
        context_str = "### VERIFIED CONTEXT\n"
        for _, row in context_df.head(5).iterrows():
            context_str += f"- College: {row['college']}, Branch: {row['branch']}, Closing Rank: {row['closing_rank']}\n"

    # RAG: Generation Step
    def generate():
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "system", "content": context_str} if context_str else {"role": "system", "content": "No specific context found."},
            {"role": "user", "content": user_message}
        ]
        try:
            stream = client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                messages=messages,
                stream=True
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield f"data: {json.dumps({'content': content})}\n\n"
        except Exception as e:
            logging.error(f"OpenAI Stream Error: {e}")
            yield f"data: {json.dumps({'error': 'The AI service is currently unavailable.'})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/feedback', methods=['POST'])
def feedback_route():
    data = request.json
    try:
        with open('feedback_log.csv', 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                data.get('type'),
                data.get('message'),
                data.get('response')
            ])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logging.error(f"Feedback logging failed: {e}")
        return jsonify({"status": "error"}), 500

# HTML Template embedded in the app
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CET-Mentor v2.0</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* Simple scrollbar styling for a better dark mode experience */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1f2937; }
        ::-webkit-scrollbar-thumb { background: #4b5563; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #6b7280; }
    </style>
</head>
<body class="bg-gray-900 text-gray-200 font-sans flex items-center justify-center h-screen">
    <div class="w-full max-w-3xl h-[90vh] bg-gray-800 rounded-2xl shadow-2xl flex flex-col">
        <div class="p-4 border-b border-gray-700 text-center bg-gray-900 rounded-t-2xl">
            <h1 class="text-xl font-bold text-white">CET-Mentor 2.0</h1>
            <p class="text-sm text-purple-400">Your AI-Powered MHT-CET Admissions Assistant</p>
        </div>

        <div id="messages-container" class="flex-1 p-6 space-y-4 overflow-y-auto">
            <div class="flex justify-start">
                <div class="bg-gray-700 rounded-lg p-3 max-w-lg">
                    <p>Hello! I'm CET-Mentor. Provide your MHT-CET rank for suggestions, or ask me any question about the admissions process.</p>
                </div>
            </div>
        </div>

        <div class="p-4 border-t border-gray-700 bg-gray-900 rounded-b-2xl">
            <div class="flex items-center space-x-2">
                <input type="text" id="message-input" placeholder="Enter your rank or ask a question..." class="flex-1 bg-gray-700 border border-gray-600 rounded-full py-2 px-4 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 transition">
                <button id="send-btn" class="bg-purple-600 text-white font-bold py-2 px-5 rounded-full hover:bg-purple-700 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500">Send</button>
            </div>
        </div>
    </div>

<script>
    const messagesContainer = document.getElementById('messages-container');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    let messageCounter = 0;

    const addMessage = (html, type) => {
        const wrapper = document.createElement('div');
        wrapper.className = `flex ${type === 'user' ? 'justify-end' : 'justify-start'}`;
        
        const bubble = document.createElement('div');
        bubble.className = `rounded-lg p-3 max-w-lg ${type === 'user' ? 'bg-purple-600 text-white' : 'bg-gray-700'}`;
        bubble.innerHTML = html; // Allows for HTML content like lists and bolding
        
        wrapper.appendChild(bubble);
        messagesContainer.appendChild(wrapper);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return bubble;
    };

    const handleSend = async () => {
        const userText = messageInput.value.trim();
        if (!userText) return;
        
        addMessage(userText, 'user');
        const userMessageForApi = userText; // Keep a copy before clearing
        messageInput.value = '';

        // Smart Intent Recognition
        if (/^\\d{1,7}$/.test(userMessageForApi)) {
            await fetchSuggestions(parseInt(userMessageForApi));
        } else {
            await fetchChatResponse(userMessageForApi);
        }
    };

    const fetchSuggestions = async (rank) => {
        const thinkingBubble = addMessage('<span class="italic">Finding college suggestions...</span>', 'bot');
        try {
            const response = await fetch('/suggest', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ rank })
            });
            const data = await response.json();

            if (data.error) {
                thinkingBubble.innerHTML = `<p class="text-red-400">${data.error}</p>`;
                return;
            }
            
            let html = `For a rank of <strong>${rank}</strong>, here are some options based on past data:<br><br>`;
            if (data.safe_options.length > 0) {
                html += '<strong class="text-green-400">Good Possibilities (Cutoff Rank > Your Rank):</strong><ul class="list-disc list-inside mt-1">';
                data.safe_options.forEach(c => { html += `<li>${c.college} (Closing Rank: ${c.closing_rank})</li>`; });
                html += '</ul>';
            }
            if (data.ambitious_options.length > 0) {
                html += '<br><strong class="text-yellow-400">Ambitious Goals (Cutoff Rank < Your Rank):</strong><ul class="list-disc list-inside mt-1">';
                data.ambitious_options.forEach(c => { html += `<li>${c.college} (Closing Rank: ${c.closing_rank})</li>`; });
                html += '</ul>';
            }
            if(data.safe_options.length === 0 && data.ambitious_options.length === 0){
                html += "No specific suggestions found for this rank in the current dataset."
            }
            thinkingBubble.innerHTML = html;

        } catch (e) {
            thinkingBubble.innerHTML = '<p class="text-red-400">An error occurred while fetching suggestions.</p>';
        }
    };

    const fetchChatResponse = async (message) => {
        const botBubble = addMessage('<span class="italic opacity-75">CET-Mentor is thinking...</span>', 'bot');
        let fullResponse = "";
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            botBubble.innerHTML = ""; // Clear the thinking message

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\\n');
                lines.forEach(line => {
                    if (line.startsWith('data:')) {
                        try {
                            const data = JSON.parse(line.substring(5));
                            if (data.content) {
                                fullResponse += data.content;
                                // Basic markdown for bolding and newlines
                                botBubble.innerHTML = fullResponse.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br>');
                            }
                            if (data.error) {
                                botBubble.innerHTML = `<p class="text-red-400">${data.error}</p>`;
                            }
                        } catch (e) {}
                    }
                });
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        } catch (e) {
            botBubble.innerHTML = '<p class="text-red-400">Could not connect to the AI service.</p>';
        }
    };

    sendBtn.addEventListener('click', handleSend);
    messageInput.addEventListener('keydown', (e) => { if(e.key === 'Enter') handleSend(); });
</script>
</body>
</html>"""

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
