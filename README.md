# 🤖 Programmer's Multi-LLM Chatbot

A clean, elegant, and powerful chatbot interface built with Gradio, designed specifically for programming and advanced reasoning tasks. This application allows you to converse with top-tier Large Language Models from multiple providers in a unified interface, with support for file attachments and persistent memory.

## ✨ Features

- **Multi-Model Support**: Seamlessly switch between the best LLMs available:
  - GPT-5 (via OpenAI)
  - Claude Sonnet 4.6 (via Anthropic)
  - Gemini-3 (via Google GenAI)
  - grok-4-1-fast-reasoning (via xAI)
  - Qwen3-Coder (via compatible endpoints like DeepSeek)
- **File Parsing & Uploads**: Attach various file types for the LLMs to analyze:
  - Text & Code: `.txt`, `.py`, `.md`, `.csv`, `.json`, etc.
  - Documents: `.pdf`
  - Images: `.jpg`, `.png` (for vision-capable models)
  - Audio: `.mp3`, `.wav`
- **Persistent Memory**: Conversations are saved locally per session, allowing the chatbot to remember context throughout your discussion.
- **Elegant UI**: A beautiful, modern chat interface built using Gradio's soft theme.

## 🚀 Setup Instructions

### 1. Prerequisites
Ensure you have Python 3.8+ installed on your system.

### 2. Clone and Setup Environment
Navigate to the project directory and create a virtual environment:

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the environment (Mac/Linux)
source venv/bin/activate
# Or on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API Keys
Copy the example environment file to create your own configuration:

```bash
cp .env.example .env
```

Open `.env` and fill in your API keys for the providers you intend to use:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `XAI_API_KEY`
- `QWEN_API_KEY` (and optionally `QWEN_BASE_URL`)

### 4. Run the Application
Start the Gradio server:

```bash
python app.py
```

The application will launch and be accessible in your browser, typically at [http://127.0.0.1:7860](http://127.0.0.1:7860).

## 📁 Project Structure
- `app.py`: The main Gradio web application and UI definition.
- `llm_manager.py`: Handles routing requests to the appropriate LLM provider APIs.
- `file_parser.py`: Logic for extracting text and data from uploaded files.
- `memory_manager.py`: Manages saving and loading conversation history locally (`memory/` folder).
- `requirements.txt`: Python dependencies.
