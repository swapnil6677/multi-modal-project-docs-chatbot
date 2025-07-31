// Project ID will be set by the template
let projectId = window.projectId;

// Store current sources for modal display
let currentSources = [];
// Store all sources by chat ID for persistent access
let allChatSources = {};

// Markdown-like formatting function with source reference support
function formatAIResponse(text, sources = [], chatId = null) {
    if (!text) return '';
    
    console.log('formatAIResponse called with:', { text: text.substring(0, 200), sourcesCount: sources.length, chatId });
    
    // Convert markdown to HTML
    let formatted = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^\* (.*$)/gim, '<li>$1</li>')
        .replace(/^\d+\. (.*$)/gim, '<li>$1</li>')
        .replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>')
        .replace(/\n\n/g, '<\/p><p>')
        .replace(/\n/g, '<br>');
    
    // Convert source references - handle multiple formats
    
    // Format 1: [Source X] -> clickable reference  
    formatted = formatted.replace(/\[Source (\d+)\]/g, function(match, num) {
        const sourceIndex = parseInt(num) - 1;
        const chatIdAttr = chatId ? ` data-chat-id="${chatId}"` : '';
        return `<span class="source-reference" data-source-index="${sourceIndex}"${chatIdAttr} title="Click to view source"><strong>[${num}]</strong></span>`;
    });
    
    // Format 2: [Source X, Y, Z] -> multiple clickable references
    formatted = formatted.replace(/\[Source ([\d,\s]+)\]/g, function(match, nums) {
        const numbers = nums.split(',').map(n => n.trim()).filter(n => n && !isNaN(n));
        const chatIdAttr = chatId ? ` data-chat-id="${chatId}"` : '';
        const references = numbers.map(num => {
            const sourceIndex = parseInt(num) - 1;
            return `<span class="source-reference" data-source-index="${sourceIndex}"${chatIdAttr} title="Click to view source"><strong>[${num}]</strong></span>`;
        });
        return references.join(', ');
    });
    
    // Format 3: [X] where X is just a number -> clickable reference
    formatted = formatted.replace(/\[(\d+)\]/g, function(match, num) {
        const sourceIndex = parseInt(num) - 1;
        const chatIdAttr = chatId ? ` data-chat-id="${chatId}"` : '';
        return `<span class="source-reference" data-source-index="${sourceIndex}"${chatIdAttr} title="Click to view source"><strong>[${num}]</strong></span>`;
    });
    
    // Format 4: [X, Y, Z] -> multiple clickable references
    formatted = formatted.replace(/\[([\d,\s]+)\]/g, function(match, nums) {
        // Only process if it contains only numbers, commas, and spaces
        if (!/^[\d,\s]+$/.test(nums)) return match;
        
        const numbers = nums.split(',').map(n => n.trim()).filter(n => n && !isNaN(n));
        if (numbers.length === 0) return match;
        
        const chatIdAttr = chatId ? ` data-chat-id="${chatId}"` : '';
        const references = numbers.map(num => {
            const sourceIndex = parseInt(num) - 1;
            return `<span class="source-reference" data-source-index="${sourceIndex}"${chatIdAttr} title="Click to view source"><strong>[${num}]</strong></span>`;
        });
        return references.join(', ');
    });
    
    console.log('After source reference processing:', formatted.substring(0, 500));
    console.log('Number of source-reference spans created:', (formatted.match(/source-reference/g) || []).length);
    
    // Wrap in paragraphs
    if (!formatted.includes('<h') && !formatted.includes('<li>')) {
        formatted = '<p>' + formatted + '<\/p>';
    }
    
    // Wrap lists - Fixed regex escaping
    formatted = formatted.replace(/(<li>.*?<\/li>)/g, '<ul>$1<\/ul>');
    
    return formatted;
}

// Stream text character by character (text only, format at end)
function streamText(element, htmlContent, speed = 30) {
    return new Promise((resolve) => {
        // Extract plain text from HTML for streaming
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = htmlContent;
        const plainText = tempDiv.textContent || tempDiv.innerText;
        
        let i = 0;
        element.innerHTML = '';
        element.classList.add('typing-text');
        
        function typeChar() {
            if (i < plainText.length) {
                // Show progressive plain text with basic formatting
                const currentText = plainText.substring(0, i + 1);
                element.innerHTML = '<p>' + currentText.replace(/\n/g, '<br>') + '</p>';
                i++;
                setTimeout(typeChar, speed);
            } else {
                // Apply full HTML formatting at the end
                element.innerHTML = htmlContent;
                element.classList.remove('typing-text');
                resolve();
            }
        }
        
        typeChar();
    });
}

// Initialize sources from chat history on page load
function initializeChatSources() {
    // Get sources data from the hidden data element
    const sourcesData = document.getElementById('chat-sources-data');
    if (sourcesData) {
        try {
            allChatSources = JSON.parse(sourcesData.textContent);
            console.log('Initialized chat sources:', allChatSources);
        } catch (e) {
            console.error('Error parsing chat sources data:', e);
        }
    }
}

// Show source in modal - enhanced to work with persistent chat sources
function showSourceModal(sourceIndex, chatId = null) {
    console.log('showSourceModal called with index:', sourceIndex, 'chatId:', chatId);
    
    // Determine which sources to use
    let sourcesToUse = [];
    
    if (chatId && allChatSources[chatId]) {
        // Use sources from specific chat
        sourcesToUse = allChatSources[chatId];
        console.log('Using sources from chat', chatId, ':', sourcesToUse);
    } else if (currentSources && currentSources.length > 0) {
        // Use current sources (for new messages)
        sourcesToUse = currentSources;
        console.log('Using current sources:', sourcesToUse);
    } else {
        console.log('No sources available');
        alert('No sources available. Please ask a new question to load sources.');
        return;
    }
    
    if (sourceIndex >= sourcesToUse.length || sourceIndex < 0) {
        alert(`Source ${sourceIndex + 1} not found. Available sources: 1-${sourcesToUse.length}`);
        return;
    }
    
    const source = sourcesToUse[sourceIndex];
    console.log('Selected source:', source);
    
    const fileName = source.metadata?.file_name || source.metadata?.filename || `Document ${sourceIndex + 1}`;
    let content = source.page_content || source.content || 'No content available';
    
    // Fix content display issues - remove extra spaces between characters
    content = content.replace(/\s+/g, ' ').trim();
    
    // If content still looks garbled (too many single character words), try to clean it
    const words = content.split(' ');
    const singleCharWords = words.filter(word => word.length === 1).length;
    const totalWords = words.length;
    
    if (totalWords > 10 && (singleCharWords / totalWords) > 0.3) {
        // Likely has spacing issues, try to reconstruct
        content = content.replace(/\s+/g, '');
        // Add spaces back at logical points (after periods, before capitals, etc.)
        content = content.replace(/\./g, '. ')
                        .replace(/([a-z])([A-Z])/g, '$1 $2')
                        .replace(/([0-9])([A-Z])/g, '$1 $2')
                        .replace(/\s+/g, ' ')
                        .trim();
    }
    
    const score = source.score ? (source.score * 100).toFixed(1) + '%' : '';
    const documentPath = source.metadata?.source || source.metadata?.file_path || null;
    
    // Create modal HTML with improved styling and document access
    const modalHtml = `
        <div class="modal fade" id="sourceModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-xl">
                <div class="modal-content border-0 shadow-lg">
                    <div class="modal-header bg-light border-bottom">
                        <div class="d-flex align-items-center flex-grow-1">
                            <i class="fas fa-file-text me-2 text-primary"></i>
                            <div>
                                <h5 class="modal-title mb-0">Source ${sourceIndex + 1}: ${fileName}</h5>
                                <small class="text-muted">
                                    ${documentPath ? `📁 ${documentPath}` : 'Document excerpt'}
                                    ${score ? ` • ${score} relevance` : ''}
                                </small>
                            </div>
                        </div>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body p-0">
                        <div class="row g-0">
                            <div class="col-12">
                                <div class="p-4">
                                    <div class="d-flex justify-content-between align-items-center mb-3">
                                        <h6 class="text-muted mb-0">
                                            <i class="fas fa-quote-left me-2"></i>Document Content
                                        </h6>
                                        ${documentPath ? `
                                            <button type="button" class="btn btn-outline-primary btn-sm" onclick="openDocument('${documentPath}', '${fileName}')">
                                                <i class="fas fa-external-link-alt me-1"></i>View Full Document
                                            </button>
                                        ` : ''}
                                    </div>
                                    
                                    <!-- Show text content -->
                                    <div class="source-text-content">
                                        ${content}
                                    </div>
                                    
                                    ${source.metadata && Object.keys(source.metadata).length > 0 ? `
                                        <div class="mt-4">
                                            <h6 class="text-muted mb-3">
                                                <i class="fas fa-info-circle me-2"></i>Document Information
                                            </h6>
                                            <div class="row">
                                                ${Object.entries(source.metadata).filter(([key, value]) => key !== 'total_pages').map(([key, value]) => `
                                                    <div class="col-md-6 mb-2">
                                                        <div class="metadata-item">
                                                            <strong>${key.replace(/_/g, ' ').toUpperCase()}:</strong>
                                                            <span class="text-muted ms-1">${value}</span>
                                                        </div>
                                                    </div>
                                                `).join('')}
                                            </div>
                                        </div>
                                    ` : ''}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer bg-light">
                        <div class="d-flex justify-content-between w-100 align-items-center">
                            <small class="text-muted">
                                <i class="fas fa-lightbulb me-1"></i>
                                This excerpt was selected as most relevant to your question
                            </small>
                            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
                                <i class="fas fa-times me-1"></i>Close
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal
    const existingModal = document.getElementById('sourceModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('sourceModal'));
    modal.show();
}

// Function to open the full document in a new window/tab
function openDocument(documentPath, fileName) {
    try {
        // Try to construct a file URL for local documents
        if (documentPath.startsWith('/') || documentPath.match(/^[A-Za-z]:/)) {
            // Local file path - create file URL
            const fileUrl = `file://${documentPath}`;
            window.open(fileUrl, '_blank');
        } else if (documentPath.startsWith('http://') || documentPath.startsWith('https://')) {
            // Web URL - open directly
            window.open(documentPath, '_blank');
        } else {
            // Relative path - try to open via server
            const serverUrl = `/view-document?path=${encodeURIComponent(documentPath)}`;
            window.open(serverUrl, '_blank');
        }
    } catch (error) {
        console.error('Error opening document:', error);
        // Fallback: show an alert with the document path
        alert(`Document location: ${documentPath}\n\nPlease navigate to this location in your file manager to view the full document.`);
    }
}

// Create simplified source list (optional - for reference at bottom)
function createSourcesList(sources) {
    if (!sources || sources.length === 0) return '';
    
    let sourcesHtml = '<div class="sources-list mt-3"><h6 class="mb-2 text-muted">Sources:</h6><div class="row">';
    
    sources.forEach((source, index) => {
        const fileName = source.metadata?.file_name || `Document ${index + 1}`;
        sourcesHtml += `
            <div class="col-md-6 mb-2">
                <small class="text-muted">
                    <span class="source-reference-small" data-source-index="${index}" title="Click to view source">
                        ${index + 1}
                    </span>
                    ${fileName}
                </small>
            </div>
        `;
    });
    
    sourcesHtml += '</div></div>';
    return sourcesHtml;
}

// Create source references
function createSourceReferences(sources) {
    if (!sources || sources.length === 0) return '';
    
    let sourcesHtml = '<div class="sources-section"><h6 class="mb-2">Sources:</h6>';
    
    sources.forEach((source, index) => {
        const sourceId = `source-${Date.now()}-${index}`;
        const fileName = source.metadata?.file_name || `Document ${index + 1}`;
        const score = source.score ? (source.score * 100).toFixed(1) + '%' : '';
        const preview = source.page_content?.substring(0, 150) || '';
        
        sourcesHtml += `
            <div class="source-item" id="${sourceId}">
                <div class="source-header">
                    <span class="source-name">${fileName}</span>
                    ${score ? `<span class="source-score">${score} match</span>` : ''}
                </div>
                <div class="source-content">
                    <div class="source-preview" data-source-id="${sourceId}" style="cursor: pointer;">
                        ${preview}${preview.length >= 150 ? '...' : ''}
                        ${preview.length >= 150 ? '<small class="text-primary"> (click to expand)</small>' : ''}
                    </div>
                    <div class="source-full" id="${sourceId}-full">
                        ${source.page_content || 'No content available'}
                    </div>
                </div>
            </div>
        `;
    });
    
    sourcesHtml += '</div>';
    return sourcesHtml;
}

// Toggle source expansion
function toggleSourceFull(sourceId) {
    const fullElement = document.getElementById(sourceId + '-full');
    const previewElement = document.querySelector(`#${sourceId} .source-preview`);
    
    if (fullElement.style.display === 'none' || !fullElement.style.display) {
        fullElement.style.display = 'block';
        previewElement.innerHTML = previewElement.innerHTML.replace('(click to expand)', '(click to collapse)');
    } else {
        fullElement.style.display = 'none';
        previewElement.innerHTML = previewElement.innerHTML.replace('(click to collapse)', '(click to expand)');
    }
}

// Create animated thinking indicator
function createThinkingIndicator() {
    return `
        <div class="thinking-indicator">
            Thinking
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
}

// Create chat message element
function createChatMessage(question, answer = null, isThinking = false) {
    const timestamp = new Date().toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false
    });
    
    const answerContent = isThinking ? createThinkingIndicator() : 
                         (answer ? `<div class="formatted-response">${formatAIResponse(answer)}</div>` : '');
    
    return `
        <div class="chat-conversation mb-4">
            <!-- User Message -->
            <div class="user-message mb-3">
                <div class="d-flex align-items-start">
                    <div class="user-avatar me-3">
                        <div class="avatar-circle bg-primary text-white">
                            <i class="fas fa-user"></i>
                        </div>
                    </div>
                    <div class="message-content">
                        <div class="message-header">
                            <strong>You</strong>
                            <small class="text-muted ms-2">${timestamp}</small>
                        </div>
                        <div class="message-text">
                            ${question}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- AI Response -->
            <div class="ai-message">
                <div class="d-flex align-items-start">
                    <div class="ai-avatar me-3">
                        <div class="avatar-circle bg-success text-white">
                            <i class="fas fa-robot"></i>
                        </div>
                    </div>
                    <div class="message-content">
                        <div class="message-header">
                            <strong>AI Assistant</strong>
                            <small class="text-muted ms-2">${timestamp}</small>
                        </div>
                        <div class="message-text ai-response">
                            ${answerContent}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Initialize the application
function initializeApp() {
    // Initialize chat sources from database
    initializeChatSources();
    
    // Add click event listeners to all source references and toggles
    document.addEventListener('click', function(e) {
        // Check if clicked element or its parent is a source reference
        const sourceElement = e.target.closest('.source-reference') || 
                             (e.target.classList.contains('source-reference') ? e.target : null) ||
                             (e.target.classList.contains('source-reference-small') ? e.target : null);
        
        if (sourceElement) {
            e.preventDefault();
            const sourceIndex = parseInt(sourceElement.getAttribute('data-source-index'));
            const chatId = sourceElement.getAttribute('data-chat-id');
            showSourceModal(sourceIndex, chatId);
        } else if (e.target.classList.contains('source-preview') || e.target.closest('.source-preview')) {
            const previewElement = e.target.classList.contains('source-preview') ? e.target : e.target.closest('.source-preview');
            const sourceId = previewElement.getAttribute('data-source-id');
            if (sourceId) {
                toggleSourceFull(sourceId);
            }
        }
    });
    
    // Format existing chat responses with proper source references
    const existingResponses = document.querySelectorAll('.ai-response[data-content]');
    existingResponses.forEach(response => {
        const content = response.getAttribute('data-content');
        const chatId = response.getAttribute('data-chat-id');
        
        if (content) {
            // Get sources for this specific chat if available
            const chatSources = chatId && allChatSources[chatId] ? allChatSources[chatId] : [];
            
            // Format the content and display it directly in the response element
            response.innerHTML = formatAIResponse(content, chatSources, chatId);
            
            // Add source indicator if sources are available
            if (chatSources && chatSources.length > 0) {
                const sourceIndicator = document.createElement('div');
                sourceIndicator.className = 'sources-indicator';
                sourceIndicator.innerHTML = `
                    <i class="fas fa-info-circle info-icon"></i>
                    <span class="source-count">${chatSources.length}</span>
                    source${chatSources.length > 1 ? 's' : ''} referenced above
                    <small style="margin-left: 8px; opacity: 0.8;">Click the numbered references to view details</small>
                `;
                response.appendChild(sourceIndicator);
            }
        }
    });
}

// Upload form handler
function setupUploadForm() {
    document.getElementById('uploadForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('fileInput');
        const files = fileInput.files;
        
        if (files.length === 0) {
            alert('Please select files to upload');
            return;
        }
        
        const formData = new FormData();
        for (let file of files) {
            formData.append('files', file);
        }
        
        const uploadBtn = document.getElementById('uploadBtn');
        const uploadProgress = document.getElementById('uploadProgress');
        
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        uploadProgress.style.display = 'block';
        
        try {
            console.log('Project ID:', projectId);
            console.log('Upload URL:', `/api/projects/${projectId}/upload`);
            
            const response = await fetch(`/api/projects/${projectId}/upload`, {
                method: 'POST',
                body: formData
            });
            
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
            
            if (response.ok) {
                const result = await response.json();
                alert('Files uploaded successfully!');
                location.reload(); // Refresh page to show new documents
            } else {
                // Try to parse as JSON, fallback to text
                let errorMessage;
                try {
                    const error = await response.json();
                    errorMessage = error.error || error.message || 'Unknown error';
                } catch (e) {
                    const errorText = await response.text();
                    console.log('Response text:', errorText);
                    errorMessage = 'Server returned non-JSON response';
                }
                alert('Upload failed: ' + errorMessage);
            }
        } catch (error) {
            alert('Upload failed: ' + error.message);
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="fas fa-upload"></i> Upload & Process';
            uploadProgress.style.display = 'none';
        }
    });
}

// Question form handler with streaming and sources
function setupQuestionForm() {
    document.getElementById('questionForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const questionInput = document.getElementById('questionInput');
        const question = questionInput.value.trim();
        
        if (!question) {
            alert('Please enter a question');
            return;
        }
        
        const askBtn = document.getElementById('askBtn');
        const chatHistory = document.getElementById('chatHistory');
        
        // Clear empty state if it exists
        const emptyState = chatHistory.querySelector('.empty-state');
        if (emptyState) {
            emptyState.parentElement.remove();
        }
        
        askBtn.disabled = true;
        askBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Thinking...';
        
        // Add question and thinking indicator to chat
        const messageElement = document.createElement('div');
        messageElement.innerHTML = createChatMessage(question, null, true);
        chatHistory.appendChild(messageElement);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        
        // Clear input
        questionInput.value = '';
        
        try {
            const response = await fetch(`/api/projects/${projectId}/ask`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question: question })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('Raw API response:', result);
                
                // Get the AI response element
                const aiResponseElement = messageElement.querySelector('.ai-response');
                
                // Handle both new structured format and old string format
                let answerText = '';
                let sources = [];
                
                if (typeof result.answer === 'object' && result.answer.answer) {
                    // New structured format
                    console.log('Using new structured format');
                    answerText = result.answer.answer;
                    sources = result.answer.sources || [];
                    console.log('Extracted sources:', sources);
                } else if (typeof result.answer === 'string') {
                    // Old string format
                    console.log('Using old string format');
                    answerText = result.answer;
                    sources = result.sources || [];
                } else {
                    console.log('Unknown response format:', typeof result.answer, result.answer);
                    answerText = 'Sorry, I received an unexpected response format.';
                }
                
                // Create a container for streaming text
                const streamingContainer = document.createElement('div');
                streamingContainer.className = 'formatted-response';
                aiResponseElement.innerHTML = '';
                aiResponseElement.appendChild(streamingContainer);
                
                // Store sources globally for modal access
                currentSources = sources;
                console.log('Sources stored for modal access:', sources);
                
                // Get the chat ID from the response (if available)
                const chatId = result.chat_id || ('new_' + Date.now());
                if (sources && sources.length > 0) {
                    allChatSources[chatId] = sources;
                    // Set the chat ID in the response element for reference
                    aiResponseElement.setAttribute('data-chat-id', chatId);
                }
                
                // Stream the text with source references using the actual chat ID
                const formattedText = formatAIResponse(answerText, sources, chatId);
                await streamText(streamingContainer, formattedText, 20);
                
                // Only add source indicator if there are actual source references in the formatted text
                if (sources && sources.length > 0 && formattedText.includes('source-reference')) {
                    const sourceIndicator = document.createElement('div');
                    sourceIndicator.className = 'sources-indicator';
                    sourceIndicator.innerHTML = `
                        <i class="fas fa-info-circle info-icon"></i>
                        <span class="source-count">${sources.length}</span>
                        source${sources.length > 1 ? 's' : ''} available
                        <small style="margin-left: 8px; opacity: 0.8;">Click the numbered references above to view details</small>
                    `;
                    streamingContainer.appendChild(sourceIndicator);
                } else if (sources && sources.length > 0) {
                    // Show sources available but not referenced in text
                    const sourceIndicator = document.createElement('div');
                    sourceIndicator.className = 'sources-indicator';
                    sourceIndicator.innerHTML = `
                        <i class="fas fa-database info-icon"></i>
                        <span class="source-count">${sources.length}</span>
                        source document${sources.length > 1 ? 's' : ''} used for this answer
                        <small style="margin-left: 8px; opacity: 0.8;">Information sourced from uploaded documents</small>
                    `;
                    streamingContainer.appendChild(sourceIndicator);
                }
                
                // Scroll to bottom
                chatHistory.scrollTop = chatHistory.scrollHeight;
                
            } else {
                const error = await response.json();
                // Update with error message
                const aiResponseElement = messageElement.querySelector('.ai-response');
                aiResponseElement.innerHTML = `
                    <div class="alert alert-danger mb-0" role="alert">
                        <i class="fas fa-exclamation-triangle"></i> 
                        Error: ${error.error || 'Something went wrong'}
                    </div>
                `;
            }
        } catch (error) {
            // Update with error message
            const aiResponseElement = messageElement.querySelector('.ai-response');
            aiResponseElement.innerHTML = `
                <div class="alert alert-danger mb-0" role="alert">
                    <i class="fas fa-exclamation-triangle"></i> 
                    Network Error: ${error.message}
                </div>
            `;
        } finally {
            askBtn.disabled = false;
            askBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Ask';
        }
    });
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupUploadForm();
    setupQuestionForm();
});
