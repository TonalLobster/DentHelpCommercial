/**
 * DentalScribe AI - Framstegsspåring för transkriptionsprocessen
 *
 * Denna fil hanterar realtidsuppdateringar och visuell återkoppling
 * om framstegen i transkriptionsprocessen.
 */

class ProgressTracker {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Element med ID '${containerId}' hittades inte`);
            return;
        }
        
        // Bygg HTML-strukturen för progress-tracker
        this.createProgressUI();
        
        // Hämta DOM-referenser för de olika elementen
        this.progressBar = this.container.querySelector('.progress-bar');
        this.statusMessage = this.container.querySelector('.status-message');
        this.timeEstimate = this.container.querySelector('.time-estimate');
        this.stepElements = {
            compression: this.container.querySelector('#step-compression'),
            transcription: this.container.querySelector('#step-transcription'),
            summary: this.container.querySelector('#step-summary'),
            saving: this.container.querySelector('#step-saving')
        };
        
        // Intern state
        this.isActive = false;
        this.eventSource = null;
        this.taskId = null;
        this.pollingInterval = null;
    }
    
    /**
     * Skapa användargränssnittet för progress-tracker
     */
    createProgressUI() {
        const progressHTML = `
            <div class="progress-tracker-container">
                <div class="card shadow-sm">
                    <div class="card-header bg-light">
                        <h5 class="mb-0">
                            <i class="fas fa-tasks me-2"></i>Bearbetningsframsteg
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="progress mb-3">
                            <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                role="progressbar" style="width: 0%;" aria-valuenow="0" 
                                aria-valuemin="0" aria-valuemax="100">0%</div>
                        </div>
                        <div class="status-message mb-2">Förbereder bearbetning...</div>
                        <div class="time-estimate text-muted small">Beräknar återstående tid...</div>
                        <div class="mt-4">
                            <div class="progress-steps">
                                <div class="progress-step" id="step-compression">
                                    <i class="fas fa-file-archive text-muted me-2"></i>
                                    <span>Komprimering</span>
                                    <div class="ms-auto">
                                        <span class="status-icon"><i class="fas fa-circle text-secondary"></i></span>
                                    </div>
                                </div>
                                <div class="progress-step" id="step-transcription">
                                    <i class="fas fa-microphone text-muted me-2"></i>
                                    <span>Transkribering</span>
                                    <div class="ms-auto">
                                        <span class="status-icon"><i class="fas fa-circle text-secondary"></i></span>
                                    </div>
                                </div>
                                <div class="progress-step" id="step-summary">
                                    <i class="fas fa-file-alt text-muted me-2"></i>
                                    <span>Sammanfattning</span>
                                    <div class="ms-auto">
                                        <span class="status-icon"><i class="fas fa-circle text-secondary"></i></span>
                                    </div>
                                </div>
                                <div class="progress-step" id="step-saving">
                                    <i class="fas fa-save text-muted me-2"></i>
                                    <span>Sparar resultat</span>
                                    <div class="ms-auto">
                                        <span class="status-icon"><i class="fas fa-circle text-secondary"></i></span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        this.addStyles();
        this.container.innerHTML = progressHTML;
        this.container.style.display = 'none';
    }
    
    /**
     * Lägg till nödvändiga CSS-regler om de inte redan finns
     */
    addStyles() {
        const styleId = 'progress-tracker-styles';
        if (document.getElementById(styleId)) {
            return;
        }
        
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            .progress-tracker-container {
                margin-top: 1.5rem;
                margin-bottom: 1.5rem;
            }
            .progress-steps {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .progress-step {
                display: flex;
                align-items: center;
                padding: 10px 15px;
                border-radius: 8px;
                background-color: #f8f9fa;
                border-left: 3px solid #dee2e6;
            }
            .progress-step.active {
                background-color: #e3f2fd;
                border-left-color: #0d6efd;
            }
            .progress-step.completed {
                background-color: #e8f5e9;
                border-left-color: #4caf50;
            }
            .progress-step.error {
                background-color: #ffebee;
                border-left-color: #dc3545;
            }
            .progress-step.completed .status-icon i {
                color: #4caf50 !important;
            }
            .progress-step.active .status-icon i {
                color: #0d6efd !important;
            }
            .progress-step.error .status-icon i {
                color: #dc3545 !important;
            }
            .status-message {
                font-weight: 500;
            }
            .time-estimate {
                font-style: italic;
            }
            .progress-info {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            .file-info {
                margin-top: 1rem;
                padding: 8px 12px;
                background-color: #f8f9fa;
                border-radius: 6px;
                font-size: 0.9rem;
            }
        `;
        document.head.appendChild(style);
    }
    
    /**
     * Starta progress-tracker för en specifik transkriptionsuppgift
     * @param {string} taskId - ID för den uppgift som ska följas
     */
    start(taskId) {
        if (this.isActive) {
            this.stop();
        }
        
        this.taskId = taskId;
        this.container.style.display = 'block';
        this.isActive = true;
        this.startSSE();
        
        // Om SSE misslyckas – fallback till polling
        setTimeout(() => {
            if (!this.eventSource || this.eventSource.readyState !== 1) {
                console.log('Faller tillbaka till polling...');
                this.startPolling();
            }
        }, 2000);
    }
    
    /**
     * Starta Server-Sent Events (SSE) för realtidsuppdateringar
     */
    startSSE() {
        try {
            this.eventSource = new EventSource(`/sse/progress/${this.taskId}`);
            this.eventSource.onopen = (event) => {
                console.log('SSE anslutning öppnad');
            };
            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('SSE meddelande:', data);
                    if (data.event === 'connected') {
                        console.log('SSE ansluten, påbörjar framstegsspårning');
                    } else if (data.event === 'update') {
                        this.updateProgress(data.data);
                    } else if (data.event === 'completed') {
                        this.updateProgress(data.data);
                        setTimeout(() => {
                            if (data.data.status === 'completed') {
                                this.showCompletionMessage('Bearbetning slutförd!');
                            }
                        }, 1000);
                        this.stop();
                    } else if (data.event === 'error') {
                        this.showError(data.message || 'Ett fel inträffade');
                        this.stop();
                    }
                } catch (e) {
                    console.error('Fel vid tolkning av SSE-data:', e);
                }
            };
            this.eventSource.onerror = (event) => {
                console.error('SSE-fel:', event);
                this.eventSource.close();
                this.eventSource = null;
                if (this.isActive && !this.pollingInterval) {
                    console.log('SSE misslyckades, startar polling');
                    this.startPolling();
                }
            };
        } catch (e) {
            console.error('Kunde inte starta SSE:', e);
            this.startPolling();
        }
    }
    
    /**
     * Starta polling som fallback för att hämta framsteg
     */
    startPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
        this.pollingInterval = setInterval(() => {
            fetch(`/progress-status`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Polling error:', data.error);
                        return;
                    }
                    if (data.task_id === this.taskId) {
                        this.updateProgress(data.status);
                        if (data.status.status === 'completed' || data.status.status === 'error') {
                            if (data.status.status === 'completed') {
                                this.showCompletionMessage('Bearbetning slutförd!');
                            } else {
                                this.showError(data.status.message || 'Ett fel inträffade');
                            }
                            this.stop();
                        }
                    }
                })
                .catch(err => {
                    console.error('Fel vid polling:', err);
                });
        }, 1000);  // Polling var 1 sekund
    }
    
    /**
     * Uppdatera UI baserat på det mottagna status-objektet
     * @param {Object} status - Statusobjekt med progress, message, time_left och steps
     */
    updateProgress(status) {
        if (!status || !this.isActive) return;
        
        const progress = status.progress || 0;
        this.progressBar.style.width = `${progress}%`;
        this.progressBar.setAttribute('aria-valuenow', progress);
        this.progressBar.textContent = `${Math.round(progress)}%`;
        
        if (status.message) {
            this.statusMessage.textContent = status.message;
        }
        
        if (status.time_left !== undefined) {
            if (status.time_left > 60) {
                const minutes = Math.floor(status.time_left / 60);
                const seconds = Math.floor(status.time_left % 60);
                this.timeEstimate.textContent = `Uppskattad återstående tid: ${minutes} min ${seconds} sek`;
            } else if (status.time_left > 0) {
                this.timeEstimate.textContent = `Uppskattad återstående tid: ${Math.round(status.time_left)} sekunder`;
            } else {
                this.timeEstimate.textContent = '';
            }
        }
        
        if (status.steps) {
            for (const [stepName, stepStatus] of Object.entries(status.steps)) {
                const stepElement = this.stepElements[stepName];
                if (stepElement) {
                    stepElement.classList.remove('active', 'completed', 'error');
                    switch(stepStatus) {
                        case 'active':
                            stepElement.classList.add('active');
                            break;
                        case 'completed':
                            stepElement.classList.add('completed');
                            break;
                        case 'error':
                            stepElement.classList.add('error');
                            break;
                        case 'waiting':
                            // Ingen speciell klass
                            break;
                    }
                    const icon = stepElement.querySelector('.status-icon i');
                    if (icon) {
                        icon.className = stepStatus === 'active'
                            ? 'fas fa-spinner fa-spin text-primary'
                            : stepStatus === 'completed'
                            ? 'fas fa-check-circle text-success'
                            : stepStatus === 'error'
                            ? 'fas fa-exclamation-circle text-danger'
                            : 'fas fa-circle text-secondary';
                    }
                }
            }
        }
        
        // Visa filstorleksinformation om det finns
        if (status.size_info && (status.size_info.original || status.size_info.compressed)) {
            let fileInfo = this.container.querySelector('.file-info');
            if (!fileInfo) {
                fileInfo = document.createElement('div');
                fileInfo.className = 'file-info';
                this.container.querySelector('.card-body').appendChild(fileInfo);
            }
            const originalSize = status.size_info.original ? this.formatFileSize(status.size_info.original) : 'N/A';
            const compressedSize = status.size_info.compressed ? this.formatFileSize(status.size_info.compressed) : 'N/A';
            let compressionRate = '';
            if (status.size_info.original && status.size_info.compressed && status.size_info.original > 0) {
                const rate = (1 - (status.size_info.compressed / status.size_info.original)) * 100;
                compressionRate = ` (${rate.toFixed(1)}% komprimering)`;
            }
            fileInfo.innerHTML = `
                <div><i class="fas fa-file-audio me-2"></i><strong>Filstorlek:</strong></div>
                <div>Original: ${originalSize}</div>
                ${status.size_info.compressed ? `<div>Komprimerad: ${compressedSize}${compressionRate}</div>` : ''}
            `;
        }
        
        // Ändra färgen på progressbaren beroende på status
        if (status.status === 'completed') {
            this.progressBar.classList.remove('bg-primary', 'bg-danger');
            this.progressBar.classList.add('bg-success');
        } else if (status.status === 'error') {
            this.progressBar.classList.remove('bg-primary', 'bg-success');
            this.progressBar.classList.add('bg-danger');
        } else {
            this.progressBar.classList.remove('bg-success', 'bg-danger');
            this.progressBar.classList.add('bg-primary');
        }
    }
    
    /**
     * Formatera filstorlek (bytes) till ett läsbart format
     * @param {number} bytes - Filstorlek i bytes
     * @returns {string} Formaterad sträng
     */
    formatFileSize(bytes) {
        if (bytes < 1024) {
            return `${bytes} B`;
        } else if (bytes < 1024 * 1024) {
            return `${(bytes / 1024).toFixed(1)} KB`;
        } else if (bytes < 1024 * 1024 * 1024) {
            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        } else {
            return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
        }
    }
    
    /**
     * Visa ett meddelande när bearbetningen är slutförd
     * @param {string} message - Meddelande som ska visas
     */
    showCompletionMessage(message) {
        const completionDiv = document.createElement('div');
        completionDiv.className = 'alert alert-success mt-3';
        completionDiv.innerHTML = `
            <i class="fas fa-check-circle me-2"></i>
            <strong>${message}</strong> Omdirigerar till resultatvyn...
        `;
        this.container.querySelector('.card-body').appendChild(completionDiv);
    }
    
    /**
     * Visa felmeddelande
     * @param {string} message - Felmeddelande som ska visas
     */
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger mt-3';
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-circle me-2"></i>
            <strong>Fel:</strong> ${message}
        `;
        this.container.querySelector('.card-body').appendChild(errorDiv);
    }
    
    /**
     * Stoppa progress-tracker
     */
    stop() {
        this.isActive = false;
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
    
    /**
     * Dölj progress-tracker
     */
    hide() {
        this.stop();
        this.container.style.display = 'none';
    }
    
    /**
     * Visa progress-tracker
     */
    show() {
        this.container.style.display = 'block';
    }
    
    /**
     * Återställ progress-tracker till ursprungligt läge
     */
    reset() {
        this.stop();
        this.progressBar.style.width = '0%';
        this.progressBar.setAttribute('aria-valuenow', 0);
        this.progressBar.textContent = '0%';
        this.progressBar.classList.remove('bg-success', 'bg-danger');
        this.progressBar.classList.add('bg-primary');
        this.statusMessage.textContent = 'Förbereder bearbetning...';
        this.timeEstimate.textContent = 'Beräknar återstående tid...';
        for (const stepElement of Object.values(this.stepElements)) {
            stepElement.classList.remove('active', 'completed', 'error');
            const icon = stepElement.querySelector('.status-icon i');
            if (icon) {
                icon.className = 'fas fa-circle text-secondary';
            }
        }
        const alerts = this.container.querySelectorAll('.alert');
        for (const alert of alerts) {
            alert.remove();
        }
        const fileInfo = this.container.querySelector('.file-info');
        if (fileInfo) {
            fileInfo.remove();
        }
    }
}

// Starta progress-trackers vid DOM-laddning
document.addEventListener('DOMContentLoaded', function() {
    const uploadProgressTracker = new ProgressTracker('upload-progress');
    const recordProgressTracker = new ProgressTracker('record-progress');
    
    // Eventlistener för uppladdningsformuläret
    const uploadForm = document.querySelector('#upload form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            uploadProgressTracker.reset();
            uploadProgressTracker.show();
            const fileInput = this.querySelector('input[type="file"]');
            if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
                uploadProgressTracker.showError('Ingen fil vald');
                return;
            }
            const formData = new FormData(this);
            fetch('/transcribe', {
                method: 'POST',
                body: formData,
                headers: { 'X-Progress-Tracking': 'true' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.redirect) {
                    uploadProgressTracker.start(data.task_id);
                    setTimeout(() => {
                        window.location.href = data.redirect;
                    }, 2000);
                } else if (data.error) {
                    uploadProgressTracker.showError(data.error);
                }
            })
            .catch(error => {
                console.error('Fel vid formulärskick:', error);
                uploadProgressTracker.showError('Ett oväntat fel inträffade');
            });
        });
    }
    
    // Eventlistener för inspelningsformuläret
    const recordForm = document.querySelector('#record form');
    if (recordForm) {
        recordForm.addEventListener('submit', function(e) {
            e.preventDefault();
            recordProgressTracker.reset();
            recordProgressTracker.show();
            const audioBlob = document.getElementById('audio-blob');
            if (!audioBlob || !audioBlob.value) {
                recordProgressTracker.showError('Ingen inspelning finns');
                return;
            }
            const formData = new FormData(this);
            fetch('/transcribe', {
                method: 'POST',
                body: formData,
                headers: { 'X-Progress-Tracking': 'true' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.redirect) {
                    recordProgressTracker.start(data.task_id);
                    setTimeout(() => {
                        window.location.href = data.redirect;
                    }, 2000);
                } else if (data.error) {
                    recordProgressTracker.showError(data.error);
                }
            })
            .catch(error => {
                console.error('Fel vid formulärskick:', error);
                recordProgressTracker.showError('Ett oväntat fel inträffade');
            });
        });
    }
    
    // Vid sidladdning, kontrollera om det pågår en uppgift
    fetch('/progress-status')
        .then(response => response.json())
        .then(data => {
            if (data && data.task_id && data.status && data.status.status !== 'completed' && data.status.status !== 'error') {
                const activeTab = document.querySelector('.nav-link.active');
                if (activeTab) {
                    const targetId = activeTab.getAttribute('data-bs-target');
                    if (targetId === '#record') {
                        recordProgressTracker.start(data.task_id);
                    } else if (targetId === '#upload') {
                        uploadProgressTracker.start(data.task_id);
                    }
                }
            }
        })
        .catch(err => {
            console.error('Kunde inte kontrollera framstegsstatus:', err);
        });
});
