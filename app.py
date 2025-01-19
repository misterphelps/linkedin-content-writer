from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from pydantic import BaseModel
from typing import Optional
from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import cloudscraper
from fake_useragent import UserAgent
import logging
import json
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="LinkedIn Content Writer")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

class InputRequest(BaseModel):
    url: Optional[str] = None
    message: Optional[str] = None

class OutputResponse(BaseModel):
    response: str

def fetch_url_content(url: str) -> str:
    """Fetch and parse content from a URL with enhanced site support and debugging"""
    try:
        # Create a random user agent
        ua = UserAgent()
        user_agent = ua.random
        logger.info(f"Using User-Agent: {user_agent}")
        
        # Common headers for all requests
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',  # Remove br to avoid Brotli compression
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive'
        }
        
        # Add referer
        parsed_url = urlparse(url)
        headers['Referer'] = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        
        # Initialize cloudscraper with better browser emulation
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False,
                'desktop': True
            },
            delay=10,
            interpreter='nodejs'  # Use nodejs interpreter for better JS handling
        )
        
        logger.info(f"Fetching URL: {url}")
        logger.info(f"Headers: {json.dumps(headers, indent=2)}")
        
        # Try to get the content with increased timeout and proper encoding
        response = scraper.get(
            url, 
            headers=headers, 
            timeout=30,
            allow_redirects=True
        )
        response.raise_for_status()
        
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {json.dumps(dict(response.headers), indent=2)}")
        
        # Ensure proper encoding
        if 'charset=' in response.headers.get('content-type', '').lower():
            response.encoding = response.headers['content-type'].split('charset=')[-1].strip()
        elif response.encoding is None:
            response.encoding = response.apparent_encoding
        
        # Use html5lib parser for better compatibility
        soup = BeautifulSoup(response.text, 'html5lib')
        
        # Log the HTML structure for debugging
        logger.info("HTML Structure:")
        logger.info(soup.prettify()[:500] + "...")
        
        # Remove unwanted elements
        for element in soup.find_all(['script', 'style', 'meta', 'link', 'noscript', 'header', 'footer', 'nav', 'aside', 'iframe']):
            element.decompose()
        
        # Try multiple strategies to find the main content
        content = None
        
        # Strategy 1: Look for article content with WordPress selectors
        content_selectors = [
            {'class_': 'article-content'},
            {'class_': 'article__content'},
            {'class_': 'post-content'},
            {'class_': 'entry-content'},
            {'class_': 'content'},
            {'class_': 'main-content'},
            {'class_': 'post__content'},
            {'class_': 'post-container'},
            {'class_': 'article-body'},
            {'class_': 'article__body'},
            {'data-component-name': 'ArticleContent'},
            {'id': 'main-content'},
            {'id': 'article-content'},
            {'id': 'post-content'},
            {'role': 'main'},
            {'itemprop': 'articleBody'}
        ]
        
        for selector in content_selectors:
            content = soup.find('div', **selector) or soup.find('article', **selector)
            if content:
                logger.info(f"Found content using selector: {selector}")
                break
        
        # Strategy 2: Look for article tags
        if not content:
            article_tags = soup.find_all(['article'])
            if article_tags:
                content = max(article_tags, key=lambda x: len(str(x)))
                logger.info("Found content using article tags")
        
        # Strategy 3: Look for main tag
        if not content:
            content = soup.find('main')
            if content:
                logger.info("Found content using main tag")
        
        # Strategy 4: Look for largest div with meaningful content
        if not content:
            divs = soup.find_all('div')
            if divs:
                # Filter divs with actual content
                content_divs = [d for d in divs if len(d.get_text(strip=True)) > 200]
                if content_divs:
                    content = max(content_divs, key=lambda x: len(x.get_text(strip=True)))
                    logger.info("Found content using largest div strategy")
        
        # Extract text content
        if content:
            # Get all text elements
            text_elements = content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
            text = []
            
            # Process each element
            for element in text_elements:
                element_text = element.get_text(strip=True)
                if len(element_text) > 20:  # Skip very short snippets
                    text.append(element_text)
            
            # Join the text elements
            text = '\n\n'.join(text)
            logger.info(f"Extracted text length: {len(text)}")
            logger.info("First 200 chars of extracted text:")
            logger.info(text[:200] + "...")
        else:
            logger.warning("No main content container found, falling back to paragraphs")
            # Fallback to all paragraphs
            paragraphs = soup.find_all('p')
            text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs 
                              if len(p.get_text(strip=True)) > 20])
        
        # Clean up the text
        text = ' '.join(text.split())  # Remove extra whitespace
        
        # Limit content length but try to keep complete sentences
        max_length = 4000
        if len(text) > max_length:
            # Try to cut at the last complete sentence within the limit
            last_period = text[:max_length].rfind('.')
            if last_period > 0:
                text = text[:last_period + 1]
            else:
                text = text[:max_length]
        
        if not text or len(text.strip()) < 100:  # Consider it failed if we got very little content
            logger.error("No meaningful content found")
            raise ValueError("No meaningful content found on the page")
            
        return text
        
    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Error processing URL: {str(e)}. Try these sites instead:\n" +
                   "1. Medium.com articles\n" +
                   "2. Dev.to blog posts\n" +
                   "3. GitHub blog posts\n" +
                   "4. HackerNews posts\n" +
                   "5. Reddit r/technology posts"
        )

# Initialize the model and create the chain
def create_chain():
    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not found")
    
    model = ChatOpenAI(
        model="gpt-4-1106-preview",  # Using GPT-4 Turbo for better quality
        temperature=0.7,
        api_key=api_key
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a LinkedIn content creator able to communicate with small and medium-sized business leaders.
Although you are able to speak to all sectors, you're particularly adept at communicating with franchises, private equity firms, and B2B service firms such as accounting firms, legal firms, and consultancies.

Create a compelling, engaging LinkedIn post likely to inspire conversation and generate interest in the topic of agentic AI about the following article, and include the URL at the end: 
{web_article}

Your posts should follow this style and format:
1. Use emojis strategically (🚀, 💡, etc.) to enhance readability
2. Include a bold, attention-grabbing headline
3. Share personal insights and excitement about the topic
4. Break down complex concepts for business leaders
5. Include thought-provoking questions
6. Add a personal touch or call-to-action
7. End with relevant hashtags
8. Put the URL on its own line before the hashtags

Here's an example of the style to emulate:

🚀 **Is This the End of SaaS as We Know It for SMBs?** 

As I was diving into this fascinating article on the evolution from SaaS to "Service as Software," I couldn't help but feel a wave of excitement for the future of small and medium-sized businesses (SMBs). 🌐💡

The article illustrates how Agentic AI is poised to disrupt the traditional Software as a Service (SaaS) model by delivering end-to-end solutions tailored specifically for SMBs. Instead of merely providing tools and insights, these intelligent agents are stepping up to autonomously execute tasks, freeing up valuable time and resources for business leaders. 

Imagine a world where manual processes are streamlined and the burden of routine tasks is lifted off your shoulders. From automated tax filings to intelligent sales deal optimization, Agentic AI is making bespoke solutions affordable and accessible. 🙌✨

This shift represents a unique opportunity for SMBs to harness the power of technology without the hefty price tag typically associated with enterprise-level solutions. 

Are you curious about how Agentic AI can transform your business operations? 🤔 This is just about all I'm thinking about lately, and it's making me absolutely annoying to those closest to me. Rescue them. Drop me a message, and let's talk! 

{url}

#AgenticAI #SmallBusiness #Innovation #FutureOfWork #BusinessGrowth"""),
    ])

    chain = prompt | model | StrOutputParser()

    # Create a chain that combines prompt formatting, chat model, and output parsing
    def generate_content(inputs: dict) -> str:
        web_article = inputs.get("web_article", "")
        url = inputs.get("url", "")  # Get the URL from inputs
        return chain.invoke({"web_article": web_article, "url": url})

    return generate_content

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/process", response_model=OutputResponse)
async def process_content(request: InputRequest):
    try:
        # Fetch URL content if provided
        web_article = ""
        url = request.url
        if url:
            web_article = fetch_url_content(url)
        
        # Create and run the chain
        chain = create_chain()
        
        # Generate response
        response = chain({"web_article": web_article, "url": url})
        
        return OutputResponse(response=response)
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
