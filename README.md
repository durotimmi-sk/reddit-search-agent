Reddit Search Agent
Reddit Search Agent is a web application that automates posting, searching, and scheduling content on Reddit. It uses a FastAPI backend with PRAW for Reddit interactions and a Groq-powered AI to generate engaging posts. The React frontend provides a user-friendly interface to generate posts, edit content, and manage interactions.
Features

Post Generation: Generate subreddit-specific posts using Groq's LLM (e.g., llama3-70b-8192) with rule compliance (e.g., r/startups no-promo).
Post Scheduling: Schedule posts at regular intervals.
Search Reddit: Search subreddits for topics and export results to Excel.
Karma Boosting: Comment on posts to increase account karma.
UI Interaction: Preview, edit, and post content via a React frontend.
Subreddit Rule Compliance: Automatically adjusts posts for flair, length, and no-promo rules.

Prerequisites

Python: 3.11
Node.js: 18.x or later
Reddit Account: For API access
Groq API Key: For post generation
Git: For cloning the repo

Setup Instructions
1. Clone the Repository

bash```
  git clone https://github.com/durotimmi-sk/reddit-search-agent.git
  cd reddit-search-agent
```
2. Backend Setup

Install Python Dependencies:

bash```
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
```
Ensure requirements.txt includes:
fastapi
uvicorn
praw
python-dotenv
groq
openpyxl


Configure Environment Variables:Create a .env file in the root directory:

bash```
  nano .env
```

Add:
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_user_agent
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
GROQ_API_KEY=your_groq_api_key


Get Reddit API credentials: Reddit Apps.
Get Groq API key: Groq Console.

Run the Backend:

bash```
  uvicorn app.main:app --host 0.0.0.0 --port 8000
```


3. Frontend Setup

Navigate to Frontend:

bash```
  cd frontend
```

Install Node.js Dependencies:

bash```
  npm install
```

Run the Frontend:

bash```
  npm start
```

Opens http://localhost:3000 in your browser.



4. Verify Setup

Access the UI at http://localhost:3000.
Test API: curl http://localhost:8000/health (should return {"status": "ok"}).

Usage
UI Interaction

Open UI: Visit http://localhost:3000.
Generate Post:
Enter: generate post for startups about AI agents.
Preview post, then click "Post to Reddit", "Edit", or "Cancel".


Search Reddit:
Enter: search for AI agents in startups limit 5.
Download results as Excel.


Schedule Posts:
Enter: schedule generated post for startups about AI agents every 60 minutes.



API Endpoints

Health Check: GET /health
Handle Prompt: POST /prompt

bash```
  curl -X POST http://localhost:8000/prompt -H "Content-Type: application/json" -d '{"prompt": "generate post for startups about AI agents"}'
```

Boost Karma: POST /boost_karma

bash```
  curl -X POST http://localhost:8000/boost_karma
```


Example Commands

Generate and post:

bash```
  curl -X POST http://localhost:8000/prompt -H "Content-Type: application/json" -d '{"prompt": "post generated for startups with title AI Agents: Worth It? (i will not promote) text: AI agents are transforming startups..."}'
```

Search and export:

bash```
  curl -X POST http://localhost:8000/prompt -H "Content-Type: application/json" -d '{"prompt": "search for AI agents in startups limit 10"}'
```


Project Structure
reddit-search-agent/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── reddit_agent.py      # Reddit interaction logic
│   ├── utils.py             # Excel export utility
├── frontend/
│   ├── src/
│   │   ├── App.js           # React frontend
│   │   ├── App.css          # UI styles
│   ├── package.json         # Node.js dependencies
├── accounts/                # Reddit account JSONs (optional)
├── posts/                   # Predefined post JSONs (optional)
├── .env                    # Environment variables (not tracked)
├── .gitignore              # Git ignore rules
├── requirements.txt         # Python dependencies
├── README.md               # This file

Troubleshooting
Post Removal

Issue: Posts removed by r/startups filters.
Solution:
Check reddit-agent.log for errors.
Test on r/test: generate post for test about AI agents.
Boost karma: curl -X POST http://localhost:8000/boost_karma.
Contact r/startups mods for specific filter details.



JSON Parsing Errors

Issue: Fallback post used (Exploring AI agents...).
Solution:
Check reddit-agent.log for Raw LLM response and Error generating post.
Verify Groq API key and rate limits: curl https://api.groq.com.
Try alternative model: Edit reddit_agent.py, change model="llama3-70b-8192" to model="mixtral-8x7b-32768".



UI Errors

Issue: Edit button crashes (ReferenceError: Cannot access 'prompt').
Solution:
Ensure App.js uses window.prompt in handleEditGenerated.
Check browser console (F12) for errors.
Reinstall frontend dependencies: cd frontend && npm install.



Git Issues

Issue: Push fails.
Solution:
Verify remote: git remote -v.
Use Personal Access Token for authentication.
Reset: git fetch origin && git reset --hard origin/main.



Contributing

Fork the repo.
Create a branch: git checkout -b feature/your-feature.
Commit changes: git commit -m "Add your feature".
Push: git push origin feature/your-feature.
Open a pull request.

License
MIT License. See LICENSE for details.
Contact

GitHub: durotimmi-sk
Issues: Report bugs