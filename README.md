# LinkedIn Content Writer

This application helps generate professional LinkedIn content based on web articles and user input. It uses LangChain and OpenAI's GPT model to create engaging posts.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Running the Application

Start the server:
```bash
python app.py
```

The server will run at `http://localhost:8000`

## API Usage

### POST /process

Generate LinkedIn content based on a URL and user message.

Request body:
```json
{
    "url": "https://example.com/article" (optional),
    "message": "Your message or instructions here"
}
```

Response:
```json
{
    "response": "Generated LinkedIn content"
}
```

## Features

- URL content extraction
- OpenAI GPT-3.5 Turbo integration
- Customizable prompt template
- FastAPI backend for quick response times
- Error handling and input validation
