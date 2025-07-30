# 🤖 Flask Document Chatbot

A simple Flask application for document-based Q&A using AI with user management and project organization.

## � Quick Start

**One-command setup and run:**

```bash
python3 run_project.py
```

This script will:
- ✅ Create virtual environment
- ✅ Install all dependencies 
- ✅ Set up database with demo users
- ✅ Start the application

## � Demo Users

| Username   | Password    |
|------------|-------------|
| admin      | admin123    |
| john_doe   | password123 |
| jane_smith | password123 |
| bob_wilson | password123 |
| alice_brown| password123 |

## 📋 Requirements

- Python 3.8+
- Google AI API Key
- Pinecone API Key

## ⚙️ Configuration

1. The setup script will create `.env` from `.env.example`
2. Edit `.env` with your API keys:
   ```env
   GOOGLE_API_KEY=your-google-api-key-here
   PINECONE_API_KEY=your-pinecone-api-key-here
   PINECONE_INDEX_NAME=pdf-notes
   ```

## 🌐 Usage

1. Run `python3 run_project.py`
2. Open http://localhost:5000
3. Login with demo credentials
4. Create projects and upload PDF documents
5. Ask questions about your documents

## 🛠️ Manual Setup (if needed)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Run the app
python app.py
```

## 📁 Project Structure

```
├── app.py              # Main Flask application
├── models.py           # Database models
├── config.py           # Configuration
├── chatbot_logic.py    # AI/RAG implementation
├── requirements.txt    # Dependencies
├── run_project.py      # One-click setup script
├── templates/          # HTML templates
└── .env               # Environment variables
```

## 🎯 Features

- 🔐 User authentication
- 📁 Project-based document organization
- 📄 PDF document upload and processing
- 🤖 AI-powered question answering
- 💬 Chat history per project
- 🏢 Multi-tenant isolation

## 🆘 Troubleshooting

- **Import errors**: Run `python3 run_project.py` to reinstall dependencies
- **API errors**: Check your `.env` file has valid API keys
- **Database errors**: Delete `instance/chatbot.db` and run setup again
