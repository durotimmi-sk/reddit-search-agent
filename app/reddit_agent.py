import praw
import time
import json
import os
import logging
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv
import re
import glob
from threading import Timer
from app.utils import save_to_excel

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class RedditAgent:
    def __init__(self):
        self.logs = []
        self.accounts = self.load_accounts()
        self.posts = self.load_posts()
        self.current_account = 0
        self.current_post = 0
        self.loop_timer = None
        self.reddit = None
        self.switch_account()
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.subreddit_rules = {
            "startups": {"requires_no_promo": True, "flair_required": True, "default_flair": "I will not promote", "min_length": 250, "text_allowed": True},
            "freelance": {"requires_no_promo": False, "flair_required": False, "default_flair": None, "min_length": 0, "text_allowed": True},
            "ycombinator": {"requires_no_promo": True, "flair_required": False, "default_flair": None, "min_length": 0, "text_allowed": True},
            "technology": {"requires_no_promo": True, "flair_required": True, "default_flair": "Software", "min_length": 0, "text_allowed": False},
            "redditdev": {"requires_no_promo": False, "flair_required": False, "default_flair": None, "min_length": 0, "text_allowed": True},
            "test": {"requires_no_promo": False, "flair_required": False, "default_flair": None, "min_length": 0, "text_allowed": True}
        }
        self.fallback_flairs = {
            "startups": [
                {"flair_text": "I will not promote", "flair_template_id": None},
                {"flair_text": "Discussion", "flair_template_id": None},
                {"flair_text": "Feedback", "flair_template_id": None},
                {"flair_text": "General", "flair_template_id": None}
            ]
        }
        self.invalid_flairs = ["ban me"]
        self.log("Initialized RedditAgent with version 2025-04-22")
        self.log("Note: Using synchronous PRAW; consider Async PRAW for better performance in async environments")

    def log(self, message):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.%f")
        self.logs.append(f"[{timestamp}] {message}")
        logging.info(message)

    def act(self, action, result):
        self.log(f"🎯 ACTION: {action}\n📝 RESULT: {result}")

    def load_accounts(self):
        accounts = []
        for file in glob.glob("accounts/*.json"):
            try:
                with open(file, "r") as f:
                    accounts.append(json.load(f))
                self.log(f"Loaded account: {file}")
            except Exception as e:
                self.log(f"Error loading account {file}: {str(e)}")
        if not accounts:
            accounts.append({
                "client_id": os.getenv("REDDIT_CLIENT_ID"),
                "client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
                "user_agent": os.getenv("REDDIT_USER_AGENT"),
                "username": os.getenv("REDDIT_USERNAME"),
                "password": os.getenv("REDDIT_PASSWORD")
            })
            self.log("Loaded account from .env")
        return accounts

    def load_posts(self):
        posts = []
        for file in glob.glob("posts/*.json"):
            try:
                with open(file, "r") as f:
                    posts.append(json.load(f))
                self.log(f"Loaded post: {file}")
            except Exception as e:
                self.log(f"Error loading post {file}: {str(e)}")
        return posts

    def switch_account(self):
        if not self.accounts:
            self.log("No accounts available")
            return
        account = self.accounts[self.current_account]
        self.reddit = praw.Reddit(
            client_id=account["client_id"],
            client_secret=account["client_secret"],
            user_agent=account["user_agent"],
            username=account["username"],
            password=account["password"]
        )
        self.log(f"Switched to account: {account['username']}")
        self.current_account = (self.current_account + 1) % len(self.accounts)

    def fetch_subreddit_rules(self, subreddit):
        if subreddit in self.subreddit_rules:
            self.log(f"Using cached rules for r/{subreddit}: {self.subreddit_rules[subreddit]}")
            return self.subreddit_rules[subreddit]
        
        rules = {"requires_no_promo": False, "flair_required": False, "default_flair": None, "min_length": 0, "text_allowed": True}
        try:
            subreddit_obj = self.reddit.subreddit(subreddit)
            try:
                sub_info = subreddit_obj.__dict__
                if "submission_type" in sub_info and "link" in sub_info["submission_type"].lower():
                    rules["text_allowed"] = False
                elif hasattr(subreddit_obj, "link_only") and subreddit_obj.link_only:
                    rules["text_allowed"] = False
            except Exception as e:
                self.log(f"Error checking submission type: {str(e)}")
            
            subreddit_rules = subreddit_obj.rules.get()
            for rule in subreddit_rules.get("rules", []):
                rule_text = (rule.get("description", "") + rule.get("short_name", "")).lower()
                if any(x in rule_text for x in ["no promotion", "no advertising", "no self-promo"]):
                    rules["requires_no_promo"] = True
                if "flair" in rule_text and any(x in rule_text for x in ["required", "must"]):
                    rules["flair_required"] = True
                if "minimum" in rule_text:
                    match = re.search(r"(\d+)\s*characters?", rule_text)
                    if match:
                        rules["min_length"] = int(match.group(1))
            
            flair_choices = list(subreddit_obj.flair.link_templates.user_selectable())
            if flair_choices:
                rules["flair_required"] = True
                common_flairs = ["Discussion", "Feedback", "General", "News", "Question", "Software", "AI", "Tech", "I will not promote"]
                for flair in flair_choices:
                    if flair.get("flair_text", "").strip() in common_flairs:
                        rules["default_flair"] = flair["flair_text"].strip()
                        break
                if not rules["default_flair"] and flair_choices:
                    rules["default_flair"] = flair_choices[0]["flair_text"].strip()
            
            self.subreddit_rules[subreddit] = rules
            self.log(f"Fetched rules for r/{subreddit}: {rules}")
            return rules
        except Exception as e:
            self.log(f"Error fetching rules: {str(e)}")
            return rules

    def adjust_post_for_rules(self, subreddit, title, text, post_type, url=None):
        rules = self.fetch_subreddit_rules(subreddit)
        adjusted_title = title
        adjusted_text = text or ""
        adjusted_post_type = post_type
        adjusted_url = url
        
        if rules["requires_no_promo"] and "i will not promote" not in adjusted_title.lower():
            adjusted_title += " (i will not promote)"
            self.log(f"Added no-promo disclaimer for r/{subreddit}")
        
        if not rules["text_allowed"] and adjusted_post_type == "text":
            adjusted_post_type = "link"
            if not adjusted_url:
                adjusted_url = "https://cloud.google.com/blog/topics/developers-practitioners"
                self.log(f"Using default URL: {adjusted_url}")
            adjusted_text = ""
        
        if rules["min_length"] > 0 and adjusted_post_type == "text" and len(adjusted_text) < rules["min_length"]:
            try:
                response = self.groq_client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{
                        "role": "user",
                        "content": f"Extend this text to at least {rules['min_length']} characters while keeping it relevant to the topic and suitable for r/{subreddit}. Avoid promotion:\n\n{adjusted_text}"
                    }],
                    max_tokens=500
                )
                adjusted_text = response.choices[0].message.content.strip()
                self.log(f"Extended text to {len(adjusted_text)} chars")
            except Exception as e:
                self.log(f"Error extending text: {str(e)}")
                filler = "This post has been extended to meet the minimum length requirement. " * 5
                adjusted_text += " " + filler[:rules["min_length"] - len(adjusted_text)]
                self.log(f"Used filler text to reach {len(adjusted_text)} chars")
        
        return adjusted_title, adjusted_text, rules["default_flair"], adjusted_post_type, adjusted_url

    def generate_post_content(self, subreddit, topic):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                rules = self.fetch_subreddit_rules(subreddit)
                prompt = (
                    f"Generate a Reddit post for r/{subreddit} about '{topic}'. "
                    f"Create a catchy title (50-100 chars) and a detailed body (at least {rules['min_length']} chars). "
                    f"Match the subreddit's tone: conversational and entrepreneurial for startups, technical for redditdev. "
                    f"Include specific examples or use cases (e.g., for AI agents, mention automation or research tools). "
                    f"Do not promote products or services. "
                    f"End with an engaging question to spark discussion. "
                    f"Include '(i will not promote)' in the title if required. "
                    f"Return only valid JSON wrapped in a code block, like this:\n"
                    f"```json\n{{\"title\": \"AI Agents: Startup Impact? (i will not promote)\", \"text\": \"AI agents are transforming startups...\"}}\n```"
                    f"\nDo not include any text outside the JSON code block."
                )
                response = self.groq_client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000
                )
                content = response.choices[0].message.content.strip()
                self.log(f"Attempt {attempt + 1} - Raw LLM response (length: {len(content)}): {content}")
                # Try extracting JSON from code block
                json_match = re.search(r'```json\n([\s\S]*?)\n```', content)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    self.log(f"Attempt {attempt + 1} - No JSON block found, attempting raw JSON parse")
                    json_str = content.strip()
                parsed = json.loads(json_str)
                title = parsed["title"]
                text = parsed["text"]
                self.log(f"Generated post for r/{subreddit}: {title}")
                return title, text
            except Exception as e:
                self.log(f"Attempt {attempt + 1} - Error generating post: {str(e)}")
                if attempt < max_retries - 1:
                    self.log(f"Retrying... ({attempt + 2}/{max_retries})")
                    time.sleep(2)  # Increased delay to avoid rate limits
                else:
                    self.log("Max retries reached, using fallback post")
                    fallback_title = f"{topic} Insights? (i will not promote)"
                    fallback_text = (
                        f"Exploring {topic} in {subreddit}. For example, a SaaS startup could use AI agents to automate 80% of customer support, saving hours. "
                        f"Or analyze market trends for e-commerce, spotting demand spikes. But setup costs (~$10k) and integration complexity are hurdles. "
                        f"What are your experiences with {topic} in {subreddit}? Worth it? Let's discuss! (i will not promote)"
                    )
                    return fallback_title, fallback_text

    def create_post(self, subreddit, post_type, title, text=None, url=None, image_path=None, poll_options=None, poll_duration=None):
        self.log(f"Creating {post_type} post in r/{subreddit}")
        post_ids = []
        for attempt in range(3):
            try:
                subreddit_obj = self.reddit.subreddit(subreddit)
                adjusted_title, adjusted_text, default_flair, adjusted_post_type, adjusted_url = self.adjust_post_for_rules(subreddit, title, text, post_type, url)
                self.log(f"Post details: Type={adjusted_post_type}, Title={adjusted_title}, URL={adjusted_url}")

                rules = self.fetch_subreddit_rules(subreddit)
                flair_id = None
                if rules["flair_required"]:
                    try:
                        flair_choices = list(subreddit_obj.flair.link_templates.user_selectable())
                        flair_list = [f["flair_text"].strip() for f in flair_choices]
                        self.log(f"Available flairs for r/{subreddit}: {flair_list}")
                        
                        if not flair_list or all(f.lower() in self.invalid_flairs for f in flair_list):
                            flair_choices = self.fallback_flairs.get(subreddit, [])
                            flair_list = [f["flair_text"] for f in flair_choices]
                            self.log(f"Using fallback flairs: {flair_list}")
                        
                        flair_id = next(
                            (f["flair_template_id"] for f in flair_choices if f["flair_text"].strip().lower() == default_flair.lower()),
                            None
                        )
                        if not flair_id:
                            default_flair = next(
                                (f["flair_text"] for f in flair_choices if f["flair_text"].strip().lower() not in self.invalid_flairs),
                                "I will not promote"
                            )
                        self.log(f"Selected flair: {default_flair}, ID: {flair_id}")
                    except Exception as e:
                        self.log(f"Flair fetch error: {str(e)}")
                        default_flair = "I will not promote"

                submission = None
                if adjusted_post_type == "text":
                    submission = subreddit_obj.submit(title=adjusted_title, selftext=adjusted_text, flair_id=flair_id)
                elif adjusted_post_type == "link":
                    submission = subreddit_obj.submit(title=adjusted_title, url=adjusted_url, flair_id=flair_id)
                elif adjusted_post_type == "image":
                    submission = subreddit_obj.submit_image(title=adjusted_title, image_path=image_path, flair_id=flair_id)
                elif adjusted_post_type == "poll":
                    submission = subreddit_obj.submit_poll(
                        title=adjusted_title,
                        selftext=adjusted_text,
                        options=poll_options,
                        duration=poll_duration,
                        flair_id=flair_id
                    )
                
                if not flair_id and default_flair and rules["flair_required"]:
                    try:
                        submission.flair.select(flair_text=default_flair)
                        self.log(f"Applied flair '{default_flair}' post-submission")
                    except Exception as e:
                        self.log(f"Post-submission flair failed: {str(e)}")
                
                post_ids.append(submission.id)
                post_url = f"https://www.reddit.com/r/{subreddit}/comments/{submission.id}"
                self.act("Create post", f"Posted to r/{subreddit} - ID: {submission.id}, URL: {post_url}")
                return post_ids
            except Exception as e:
                self.log(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < 2:
                    self.switch_account()
                    time.sleep(5)
                else:
                    self.act("Create post", f"Failed to post to r/{subreddit}: {str(e)}")
                    return []
        return post_ids

    def schedule_posts(self, delay_minutes, subreddit=None, topic=None):
        if self.loop_timer:
            self.loop_timer.cancel()
        if subreddit and topic:
            title, text = self.generate_post_content(subreddit, topic)
            post_ids = self.create_post(
                subreddit=subreddit,
                post_type="text",
                title=title,
                text=text
            )
            if post_ids:
                self.log(f"Scheduled generated post successful: {title}")
        elif self.posts:
            self.current_post = (self.current_post + 1) % len(self.posts)
            post = self.posts[self.current_post]
            post_ids = self.create_post(
                subreddit=post["subreddit"],
                post_type=post["type"],
                title=post["title"],
                text=post.get("text"),
                url=post.get("url"),
                image_path=post.get("image_path"),
                poll_options=post.get("poll_options"),
                poll_duration=post.get("poll_duration")
            )
            if post_ids:
                self.log(f"Scheduled post successful: {post['title']}")
        else:
            self.log("No posts available for scheduling")
            return
        self.loop_timer = Timer(delay_minutes * 60, self.schedule_posts, [delay_minutes, subreddit, topic])
        self.loop_timer.start()
        self.log(f"Next post scheduled in {delay_minutes} minutes")

    def search_reddit(self, topic, subreddits, limit):
        self.log(f"Searching for '{topic}' in r/{subreddits}")
        results = []
        try:
            subreddit = self.reddit.subreddit(subreddits)
            submissions = list(subreddit.search(query=topic, sort="relevance", time_filter="all", limit=limit))
            for submission in submissions:
                summary = self.groq_client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{"role": "user", "content": f"Summarize: Title: {submission.title}\nBody: {submission.selftext[:1000]}"}],
                    max_tokens=150
                ).choices[0].message.content
                results.append({
                    "Title": submission.title,
                    "Subreddit": submission.subreddit.display_name,
                    "URL": submission.url,
                    "Summary": summary,
                    "Post ID": submission.id
                })
            self.log(f"Found {len(results)} posts")
            return results
        except Exception as e:
            self.log(f"Search error: {str(e)}")
            return []

    def download_search_results(self, results):
        if not results:
            self.log("No search results to download")
            return None
        try:
            filename = save_to_excel(results)
            self.log(f"Search results saved to {filename}")
            return filename
        except Exception as e:
            self.log(f"Error saving results to Excel: {str(e)}")
            return None

    def post_reply(self, post_id, reply_text):
        try:
            submission = self.reddit.submission(id=post_id)
            comment = submission.reply(reply_text)
            self.act("Post reply", f"Replied to {post_id}, Comment ID: {comment.id}")
            return True
        except Exception as e:
            self.act("Post reply", f"Failed to reply to {post_id}: {str(e)}")
            return False

    def boost_karma(self):
        for sub in ["test", "learnpython"]:
            try:
                for submission in self.reddit.subreddit(sub).new(limit=5):
                    submission.reply("Great post, thanks!")
                    self.log(f"Commented on {submission.id}")
                    time.sleep(15)
            except Exception as e:
                self.log(f"Karma boost error: {str(e)}")
        karma = self.reddit.user.me().comment_karma
        self.log(f"Current comment karma: {karma}")
        return karma

    def handle_prompt(self, prompt, search_results=None, url=None, image_path=None, poll_options=None, poll_duration=None):
        parsed = self.parse_prompt(prompt, link=url)
        if parsed["intent"] == "search":
            results = self.search_reddit(parsed["topic"], parsed["subreddits"], parsed.get("limit", 5))
            download_file = self.download_search_results(results)
            return {
                "message": "Search results",
                "results": results,
                "post_ids": None,
                "download_file": download_file,
                "logs": self.logs,
                "instructions": (
                    "To get more results, use: 'search for <topic> in <subreddit> limit <number>'\n"
                    "To reply to a post, use: 'reply to post <Post ID> with <text>' or click 'Reply' in the UI\n"
                    "To generate a post, use: 'generate post for <subreddit> about <topic>'\n"
                    "To post a generated post, use: 'post generated for <subreddit> with title <title> text: <text>'\n"
                    "Other prompts:\n"
                    "- Post: 'post to <subreddit> with title <title> text: <text>'\n"
                    "- Poll: 'post to <subreddit> with poll title <title> options <opt1>,<opt2> duration <days>'\n"
                    "- Schedule: 'schedule posts every <minutes> minutes'\n"
                    "- Schedule generated: 'schedule generated post for <subreddit> about <topic> every <minutes> minutes'"
                )
            }
        elif parsed["intent"] == "reply":
            if not parsed.get("post_id") and not search_results:
                return {
                    "message": "No search results or post ID provided",
                    "results": None,
                    "post_ids": None,
                    "download_file": None,
                    "logs": self.logs
                }
            if parsed.get("post_id"):
                success = self.post_reply(parsed["post_id"], parsed["reply_text"])
                return {
                    "message": "Reply posted" if success else "Reply failed",
                    "results": None,
                    "post_ids": None,
                    "download_file": None,
                    "logs": self.logs
                }
            successes = sum(self.post_reply(post["Post ID"], parsed["reply_text"]) for post in search_results)
            return {
                "message": f"Replied to {successes} posts",
                "results": None,
                "post_ids": None,
                "download_file": None,
                "logs": self.logs
            }
        elif parsed["intent"] == "generate":
            title, text = self.generate_post_content(parsed["subreddit"], parsed["topic"])
            return {
                "message": "Generated post preview",
                "results": [{"Title": title, "Text": text, "Subreddit": parsed["subreddit"]}],
                "post_ids": None,
                "download_file": None,
                "logs": self.logs,
                "instructions": (
                    "Review the generated post above. To post it, use:\n"
                    f"'post generated for {parsed['subreddit']} with title {title} text: {text}'\n"
                    "To edit, modify the title/text and use the post command. To cancel, do nothing."
                )
            }
        elif parsed["intent"] == "post_generated":
            post_ids = self.create_post(
                subreddit=parsed["subreddit"],
                post_type="text",
                title=parsed["title"],
                text=parsed["text"]
            )
            return {
                "message": "Post created" if post_ids else "Post failed",
                "results": None,
                "post_ids": post_ids,
                "download_file": None,
                "logs": self.logs
            }
        elif parsed["intent"] == "post":
            post_ids = self.create_post(
                subreddit=parsed["subreddits"],
                post_type=parsed["post_type"],
                title=parsed["title"],
                text=parsed["text"],
                url=parsed.get("url") or url,
                image_path=image_path,
                poll_options=poll_options,
                poll_duration=poll_duration
            )
            return {
                "message": "Post created" if post_ids else "Post failed",
                "results": None,
                "post_ids": post_ids,
                "download_file": None,
                "logs": self.logs
            }
        elif parsed["intent"] == "schedule":
            self.schedule_posts(parsed["delay"], parsed.get("subreddit"), parsed.get("topic"))
            subreddit_info = ""
            if parsed.get("subreddit"):
                subreddit_info = f" for r/{parsed.get('subreddit')} about {parsed.get('topic')}"
            message = f"Scheduled {'generated ' if parsed.get('subreddit') else ''}posts every {parsed['delay']} minutes{subreddit_info}"
            return {
                "message": message,
                "results": None,
                "post_ids": None,
                "download_file": None,
                "logs": self.logs
            }
        return {
            "message": "Invalid prompt",
            "results": None,
            "post_ids": None,
            "download_file": None,
            "logs": self.logs
        }

    def parse_prompt(self, prompt, link=None):
        prompt_lower = prompt.lower().strip()
        # Generate post
        if "generate post for" in prompt_lower:
            try:
                parts = prompt_lower.split("generate post for ")[1].strip()
                subreddit, topic = parts.split(" about ", 1)
                return {
                    "intent": "generate",
                    "subreddit": subreddit.strip(),
                    "topic": topic.strip()
                }
            except:
                return {"intent": "unknown", "message": "Invalid generate post format"}
        # Post generated
        if "post generated for" in prompt_lower:
            try:
                parts = prompt_lower.split("post generated for ")[1].strip()
                subreddit = parts.split(" with title ")[0].strip()
                title = parts.split("title ")[1].split(" text: ")[0].strip()
                text = parts.split("text: ")[1].strip()
                return {
                    "intent": "post_generated",
                    "subreddit": subreddit,
                    "title": title,
                    "text": text
                }
            except:
                return {"intent": "unknown", "message": "Invalid post generated format"}
        # Search
        if "search for" in prompt_lower:
            try:
                parts = prompt_lower.split("search for ")[1].strip()
                topic = parts
                subreddits = "all"
                limit = 5
                if " in " in parts:
                    topic, rest = parts.split(" in ", 1)
                    subreddits = rest.strip()
                    if " limit " in subreddits:
                        subreddits, limit_part = subreddits.split(" limit ", 1)
                        limit = int(limit_part.strip())
                    subreddits = subreddits.strip()
                topic = topic.strip()
                return {
                    "intent": "search",
                    "topic": topic,
                    "subreddits": subreddits,
                    "limit": limit
                }
            except Exception as e:
                return {"intent": "unknown", "message": f"Invalid search format: {str(e)}"}
        # Reply
        if "reply to post" in prompt_lower:
            try:
                parts = prompt_lower.split("reply to post ")[1].strip()
                post_id, reply_text = parts.split(" with ", 1)
                return {
                    "intent": "reply",
                    "post_id": post_id.strip(),
                    "reply_text": reply_text.strip()
                }
            except:
                return {"intent": "unknown", "message": "Invalid reply format"}
        if "reply to all with" in prompt_lower:
            reply_text = prompt_lower.split("reply to all with ")[1].strip()
            return {"intent": "reply", "reply_text": reply_text}
        # Schedule
        if "schedule generated post for" in prompt_lower:
            try:
                parts = prompt_lower.split("schedule generated post for ")[1].strip()
                subreddit_topic, delay_part = parts.split(" every ", 1)
                subreddit, topic = subreddit_topic.split(" about ", 1)
                delay = float(delay_part.split(" minute")[0].strip())
                return {
                    "intent": "schedule",
                    "subreddit": subreddit.strip(),
                    "topic": topic.strip(),
                    "delay": delay
                }
            except:
                return {"intent": "unknown", "message": "Invalid schedule format"}
        if "schedule posts every" in prompt_lower:
            try:
                delay = float(prompt_lower.split("every")[1].split("minute")[0].strip())
                return {"intent": "schedule", "delay": delay}
            except:
                return {"intent": "unknown", "message": "Invalid schedule format"}
        # Poll
        if "post to" in prompt_lower and "options" in prompt_lower:
            try:
                subreddit = prompt_lower.split("post to ")[1].split(" with ")[0].strip()
                title = prompt_lower.split("title ")[1].split(" options ")[0].strip()
                options = prompt_lower.split("options ")[1].split(" duration ")[0].strip().split(",")
                duration = int(prompt_lower.split("duration ")[1].strip())
                return {
                    "intent": "post",
                    "subreddits": subreddit,
                    "post_type": "poll",
                    "title": title,
                    "poll_options": [opt.strip() for opt in options],
                    "poll_duration": duration
                }
            except:
                return {"intent": "unknown", "message": "Invalid poll format"}
        # Post
        if "post to" in prompt_lower:
            try:
                subreddit = prompt_lower.split("post to ")[1].split(" with ")[0].strip()
                title = prompt_lower.split("title ")[1].split(" text: ")[0].strip()
                text = prompt_lower.split("text: ")[1].strip()
                return {
                    "intent": "post",
                    "subreddits": subreddit,
                    "post_type": "text",
                    "title": title,
                    "text": text
                }
            except:
                return {"intent": "unknown", "message": "Invalid post format"}
        return {"intent": "unknown", "message": "Invalid prompt"}