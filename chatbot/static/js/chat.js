document.addEventListener('DOMContentLoaded', function() {
    let currentMessages = [];
    let currentEventId = null;
    let currentPhase = null;

    // Function to add a new message to the chat
    function addMessage(content, type) {
        const message = {
            content: content,
            type: type,
            timestamp: new Date().toLocaleString()
        };
        currentMessages.push(message);
        const messageDiv = createMessageElement(message);
        document.getElementById('chat-messages').appendChild(messageDiv);
        return message;
    }

    // Function to load phase history
    window.loadPhaseHistory = function(eventId, phase) {
        currentEventId = eventId;
        currentPhase = phase;
        
        fetch(`/chatbot/chat/history/${eventId}/${phase}/`)
            .then(response => response.json())
            .then(data => {
                const historyContainer = document.getElementById('chat-messages');
                historyContainer.innerHTML = ''; // Clear existing messages
                currentMessages = []; // Reset current messages
                
                // Add phase title
                const phaseTitle = document.createElement('h5');
                phaseTitle.className = 'mb-3';
                phaseTitle.textContent = data.phase_display;
                historyContainer.appendChild(phaseTitle);
                
                // Add messages
                if (data.messages && Array.isArray(data.messages)) {
                    data.messages.forEach(message => {
                        currentMessages.push(message);
                        const messageDiv = createMessageElement(message);
                        historyContainer.appendChild(messageDiv);
                    });
                }
                
                // Scroll to bottom
                historyContainer.scrollTop = historyContainer.scrollHeight;
            })
            .catch(error => {
                console.error('Error loading phase history:', error);
            });
    };

    // Function to create message element
    function createMessageElement(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.type}-message mb-3 p-3 rounded`;
        
        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp text-muted small mb-1';
        timestamp.textContent = message.timestamp;
        
        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = message.content;
        
        messageDiv.appendChild(timestamp);
        messageDiv.appendChild(content);
        return messageDiv;
    }

    // Function to load phase sessions
    window.loadPhaseSessions = function(eventId, phase) {
        currentEventId = eventId;
        currentPhase = phase;
        
        fetch(`/chatbot/api/sessions/${eventId}/${phase}/`)
            .then(response => response.json())
            .then(data => {
                const sessionsContainer = document.getElementById('phase-sessions');
                if (!sessionsContainer) return;
                
                sessionsContainer.innerHTML = ''; // Clear existing sessions
                
                if (data.success && data.sessions && data.sessions.length > 0) {
                    data.sessions.forEach(session => {
                        const sessionDiv = document.createElement('div');
                        sessionDiv.className = 'session-item d-flex justify-content-between align-items-center p-3 mb-2 bg-dark rounded';
                        
                        const leftDiv = document.createElement('div');
                        leftDiv.className = 'd-flex flex-column';
                        
                        const titleSpan = document.createElement('span');
                        titleSpan.textContent = session.title;
                        
                        const dateSpan = document.createElement('span');
                        dateSpan.className = 'text-muted small me-3';
                        dateSpan.textContent = session.formatted_date;
                        
                        leftDiv.appendChild(titleSpan);
                        leftDiv.appendChild(dateSpan);
                        
                        const viewButton = document.createElement('button');
                        viewButton.className = 'btn btn-primary btn-sm';
                        viewButton.textContent = 'View Session';
                        viewButton.onclick = () => window.location.href = `/session/${session.id}`;
                        
                        sessionDiv.appendChild(leftDiv);
                        sessionDiv.appendChild(viewButton);
                        sessionsContainer.appendChild(sessionDiv);
                    });
                } else {
                    const noSessionsDiv = document.createElement('div');
                    noSessionsDiv.className = 'text-center p-3';
                    noSessionsDiv.innerHTML = `
                        <div class="text-danger mb-2"><i class="bi bi-exclamation-circle"></i> No sessions found for this phase</div>
                        <button class="btn btn-primary btn-sm" onclick="window.location.reload()">
                            <i class="bi bi-arrow-clockwise"></i> Try Again
                        </button>
                    `;
                    sessionsContainer.appendChild(noSessionsDiv);
                }
            })
            .catch(error => {
                console.error('Error loading phase sessions:', error);
                const sessionsContainer = document.getElementById('phase-sessions');
                if (sessionsContainer) {
                    sessionsContainer.innerHTML = `
                        <div class="text-danger text-center p-3">
                            <i class="bi bi-exclamation-circle"></i> Error loading sessions
                            <button class="btn btn-primary btn-sm ms-2" onclick="loadPhaseSessions('${eventId}', '${phase}')">
                                <i class="bi bi-arrow-clockwise"></i> Retry
                            </button>
                        </div>
                    `;
                }
            });
    };

    // Function to switch phases
    window.switchPhase = function(eventId, phase) {
        // Update active tab
        document.querySelectorAll('.phase-tab').forEach(tab => {
            tab.classList.remove('active');
            if (tab.getAttribute('data-phase') === phase) {
                tab.classList.add('active');
            }
        });
        
        // Load phase sessions
        loadPhaseSessions(eventId, phase);
        
        // Update current phase
        currentPhase = phase;
    };

    // Initialize phase loading on page load
    document.addEventListener('DOMContentLoaded', function() {
        const eventId = document.querySelector('[data-event-id]')?.getAttribute('data-event-id');
        const initialPhase = document.querySelector('.phase-tab.active')?.getAttribute('data-phase');
        
        if (eventId && initialPhase) {
            loadPhaseSessions(eventId, initialPhase);
        }
    });

    // Save chat functionality
    document.getElementById('save-chat')?.addEventListener('click', function() {
        if (!currentEventId || !currentPhase || currentMessages.length === 0) {
            alert('No messages to save!');
            return;
        }

        const data = {
            event_id: currentEventId,
            phase: currentPhase,
            messages: currentMessages.map(msg => ({
                content: msg.content,
                type: msg.type
            }))
        };

        console.log('Saving chat with:', data);

        fetch('/chatbot/chat/save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(data)
        })
        .then(response => {
            console.log('Response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Response data:', data);
            if (data.success) {
                alert('Chat saved successfully!');
            } else {
                alert('Failed to save chat: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error saving chat:', error);
            alert('Failed to save chat. Please check the console for details and try again.');
        });
    });

    // Function to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Handle chat form submission
    document.getElementById('chat-form')?.addEventListener('submit', function(e) {
        e.preventDefault();
        const input = document.getElementById('user-input');
        const message = input.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage(message, 'user');
        input.value = '';

        // Send message to server
        fetch('/chatbot/chat/response/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ 
                message: message,
                event_id: currentEventId,
                phase: currentPhase
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.response) {
                // Add AI response to chat
                addMessage(data.response, 'assistant');
                // Scroll to bottom
                const chatMessages = document.getElementById('chat-messages');
                chatMessages.scrollTop = chatMessages.scrollHeight;
            } else if (data.error) {
                console.error('Error:', data.error);
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to get response. Please try again.');
        });
    });
});
