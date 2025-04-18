// frontend/src/App.js
import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { MessageCircle, Send, Image as ImageIcon, X } from 'lucide-react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hi, I'm your Reddit Search Agent. Try searching, posting, or scheduling on Reddit!",
      timestamp: new Date(),
      status: 'complete'
    }
  ]);
  const [userInput, setUserInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const [showSuggestions, setShowSuggestions] = useState(true);

  const suggestions = [
    "Search for AI agents in startups",
    "Generate post for startups about AI agents",
    "Post to startups with title AI Ideas text: Discuss AI",
    "Reply to post 1jfxanf with Great idea!",
    "Schedule generated post for startups about AI agents every 10 minutes",
    "Post to test with poll title Test Poll options Yes,No duration 3"
  ];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (userInput.trim() === '') return;

    const newMessage = {
      role: 'user',
      content: userInput,
      timestamp: new Date(),
      status: 'complete'
    };
    setMessages([...messages, newMessage]);
    setIsLoading(true);
    setUserInput('');
    setShowSuggestions(false);

    try {
      const response = await axios.post('http://localhost:8000/chat', {
        prompt: userInput,
        search_results: messages.filter(m => m.results).slice(-1)[0]?.results || null
      }, {
        headers: { 'Content-Type': 'application/json' }
      });
      const { message, results, post_ids, download_file, instructions } = response.data;
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: message,
        timestamp: new Date(),
        status: 'complete',
        results,
        post_ids,
        download_file,
        instructions
      }]);
    } catch (error) {
      console.error('Axios error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${error.message}`,
        timestamp: new Date(),
        status: 'complete'
      }]);
    }
    setIsLoading(false);
  };

  const handleSuggestionClick = (suggestion) => {
    setUserInput(suggestion);
    setShowSuggestions(false);
  };

  const handleReply = (postId) => {
    const replyText = prompt(`Enter reply for post ${postId}:`);
    if (replyText) {
      setUserInput(`reply to post ${postId} with ${replyText}`);
      handleSendMessage();
    }
  };

  const handlePostGenerated = async (subreddit, title, text) => {
    const prompt = `post generated for ${subreddit} with title ${title} text: ${text}`;
    setUserInput(prompt);
    await handleSendMessage();
  };

  const handleEditGenerated = (subreddit, title, text) => {
    const newTitle = window.prompt("Edit title:", title) || title;
    const newText = window.prompt("Edit text:", text) || text;
    const promptText = `post generated for ${subreddit} with title ${newTitle} text: ${newText}`;
    setUserInput(promptText);
    handleSendMessage();
  };

  const handleCancelGenerated = () => {
    setMessages(prev => prev.filter(msg => !msg.results || !msg.results[0].Text));
  };

  const renderSuggestions = () => {
    if (!showSuggestions || messages.length > 1) return null;
    return (
      <div className="suggestions">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => handleSuggestionClick(suggestion)}
            className="suggestion-button"
          >
            {suggestion}
          </button>
        ))}
      </div>
    );
  };

  return (
    <div className="app">
      <div className="header">
        <h1>Reddit Search Agent</h1>
        <button onClick={() => setMessages(messages.slice(0, 1))} title="Clear chat">
          <X size={18} />
        </button>
      </div>

      <div className="chat-container">
        {renderSuggestions()}
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            {message.role === 'assistant' && (
              <div className="avatar">
                <MessageCircle size={16} />
              </div>
            )}
            <div className="message-content">
              <div className="text">{message.content}</div>
              {message.results && (
                <div className="results">
                  {message.results.map((post, idx) => (
                    <div key={idx} className="post">
                      {post.Text ? (
                        <>
                          <h3>{post.Title}</h3>
                          <p><strong>r/{post.Subreddit}</strong></p>
                          <p>{post.Text}</p>
                          <div className="post-actions">
                            <button
                              onClick={() => handlePostGenerated(post.Subreddit, post.Title, post.Text)}
                              className="action-button"
                            >
                              Post to Reddit
                            </button>
                            <button
                              onClick={() => handleEditGenerated(post.Subreddit, post.Title, post.Text)}
                              className="action-button"
                            >
                              Edit
                            </button>
                            <button
                              onClick={handleCancelGenerated}
                              className="action-button"
                            >
                              Cancel
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <a href={post.URL} target="_blank" rel="noopener noreferrer">
                            {post.Title}
                          </a>
                          <p><strong>r/{post.Subreddit}</strong>: {post.Summary}</p>
                          <p><em>Post ID: {post['Post ID']}</em></p>
                          {post.URL && post.URL.match(/\.(jpg|png)$/) && (
                            <img src={post.URL} alt="Post media" className="post-image" />
                          )}
                          <button
                            onClick={() => handleReply(post['Post ID'])}
                            className="reply-button"
                          >
                            Reply
                          </button>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {message.download_file && (
                <div className="download">
                  <a
                    href={`http://localhost:8000/files/${message.download_file}`}
                    download
                    className="download-button"
                  >
                    Download Results
                  </a>
                </div>
              )}
              {message.post_ids && (
                <div className="post-ids">
                  Post IDs: {message.post_ids.join(', ')}
                </div>
              )}
              {message.instructions && (
                <div className="instructions">
                  <p><strong>Available Commands:</strong></p>
                  <pre>{message.instructions}</pre>
                </div>
              )}
              <div className="timestamp">
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
            {message.role === 'user' && (
              <div className="avatar user">
                U
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="message assistant">
            <div className="avatar">
              <MessageCircle size={16} />
            </div>
            <div className="message-content">
              <div className="loading">
                <div></div><div></div><div></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-container">
        <input
          type="text"
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
          placeholder="Enter a Reddit prompt..."
        />
        <button className="icon-button">
          <ImageIcon size={18} />
        </button>
        <button
          onClick={handleSendMessage}
          disabled={userInput.trim() === ''}
          className="send-button"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}

export default App;