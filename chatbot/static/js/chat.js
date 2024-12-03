document.addEventListener('DOMContentLoaded', function() {
    // Function to load phase history
    window.loadPhaseHistory = function(eventId, phase) {
        fetch(`/chatbot/chat/history/${eventId}/${phase}/`)
            .then(response => response.json())
            .then(data => {
                const historyContainer = document.getElementById('chat-history');
                historyContainer.innerHTML = ''; // Clear existing messages
                
                // Add phase title
                const phaseTitle = document.createElement('h5');
                phaseTitle.className = 'mb-3';
                phaseTitle.textContent = data.phase_display;
                historyContainer.appendChild(phaseTitle);
                
                // Add messages
                data.messages.forEach(message => {
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
                    historyContainer.appendChild(messageDiv);
                });
                
                // Scroll to bottom
                historyContainer.scrollTop = historyContainer.scrollHeight;
            })
            .catch(error => {
                console.error('Error loading phase history:', error);
            });
    };
});
