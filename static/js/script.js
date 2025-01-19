document.getElementById('contentForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Get form values
    const url = document.getElementById('url').value.trim();
    const message = document.getElementById('message').value.trim();
    
    // Show loading indicator
    document.getElementById('loadingIndicator').classList.remove('hidden');
    document.getElementById('result').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');
    
    try {
        // Prepare request body (only include non-empty fields)
        const requestBody = {};
        if (url) requestBody.url = url;
        if (message) requestBody.message = message;
        
        // Make API request
        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || `HTTP error! status: ${response.status}`);
        }
        
        // Display result
        document.getElementById('generatedContent').textContent = data.response;
        document.getElementById('result').classList.remove('hidden');
        document.getElementById('result').classList.add('fade-in');
        
    } catch (error) {
        // Display error message
        const errorMessage = error.message.split('\n').map(line => 
            `<p class="mb-2">${line}</p>`
        ).join('');
        
        document.getElementById('error').innerHTML = errorMessage;
        document.getElementById('error').classList.remove('hidden');
        document.getElementById('error').classList.add('fade-in');
    } finally {
        // Hide loading indicator
        document.getElementById('loadingIndicator').classList.add('hidden');
    }
});

function copyToClipboard() {
    const content = document.getElementById('generatedContent').textContent;
    navigator.clipboard.writeText(content).then(() => {
        // Visual feedback
        const button = document.querySelector('button[onclick="copyToClipboard()"]');
        const originalText = button.textContent;
        button.textContent = 'Copied!';
        setTimeout(() => {
            button.textContent = originalText;
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text: ', err);
        alert('Failed to copy to clipboard');
    });
}
