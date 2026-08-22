// Al Roshan Restaurant — RoshanBot Chat Widget

const chatToggle = document.getElementById('chat-toggle');
const chatClose = document.getElementById('chat-close');
const chatWindow = document.getElementById('chat-window');
const chatInput = document.getElementById('chat-input');
const chatSend = document.getElementById('chat-send');
const chatMessages = document.getElementById('chat-messages');

let conversationHistory = [];

// Toggle chat window
chatToggle.addEventListener('click', () => {
  const isOpen = chatWindow.style.display !== 'none';
  chatWindow.style.display = isOpen ? 'none' : 'flex';
  chatWindow.style.flexDirection = 'column';
  if (!isOpen) chatInput.focus();
});

chatClose.addEventListener('click', () => {
  chatWindow.style.display = 'none';
});

// Send on Enter key
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

chatSend.addEventListener('click', sendMessage);

function appendMessage(role, text) {
  const wrapper = document.createElement('div');
  wrapper.className = `message ${role === 'user' ? 'user-message' : 'bot-message'}`;
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;
  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTyping() {
  const wrapper = document.createElement('div');
  wrapper.className = 'message bot-message';
  wrapper.id = 'typing-indicator';
  wrapper.innerHTML = '<div class="message-bubble typing-bubble"><span></span><span></span><span></span></div>';
  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  chatInput.value = '';
  appendMessage('user', text);
  conversationHistory.push({ role: 'user', content: text });

  showTyping();
  chatSend.disabled = true;
  chatInput.disabled = true;

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: conversationHistory.slice(-10) }),
    });

    const data = await response.json();
    removeTyping();

    if (data.reply) {
      appendMessage('bot', data.reply);
      conversationHistory.push({ role: 'assistant', content: data.reply });
    } else {
      appendMessage('bot', "Sorry, I couldn't process that. Please try again.");
    }
  } catch (err) {
    removeTyping();
    appendMessage('bot', 'Connection issue. Please check your connection and try again.');
  } finally {
    chatSend.disabled = false;
    chatInput.disabled = false;
    chatInput.focus();
  }
}
