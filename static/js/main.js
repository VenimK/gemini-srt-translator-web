document.addEventListener('DOMContentLoaded', () => {
    // Your existing JS code here, wrapped in a DOMContentLoaded listener
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('fileInput');
    const fileListBody = document.getElementById('file-list-body');
    const noFilesMessage = document.getElementById('no-files-message');
    const consoleOutput = document.getElementById('console');
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');

    const geminiApiKeyInput = document.getElementById('geminiApiKey');
    const modelSelect = document.getElementById('model');
    const tmdbApiKeyInput = document.getElementById('tmdbApiKey');
    const languageInput = document.getElementById('language');
    const languageCodeInput = document.getElementById('languageCode');
    const extractAudioCheckbox = document.getElementById('extractAudio');
    const autoFetchTmdbCheckbox = document.getElementById('autoFetchTmdb');
    const isTvSeriesCheckbox = document.getElementById('isTvSeries');
    const seriesTitleContainer = document.getElementById('seriesTitleContainer');
    const seriesTitleInput = document.getElementById('seriesTitle');
    const addTranslatorInfoCheckbox = document.getElementById('addTranslatorInfo');
    const saveConfigBtn = document.getElementById('saveConfigBtn');
    const translateBtn = document.getElementById('translateBtn');
    const fetchTmdbBtn = document.getElementById('fetchTmdbBtn');

    // New elements
    const geminiApiKey2Input = document.getElementById('geminiApiKey2');
    const batchSizeInput = document.getElementById('batchSize');
    const thinkingBudgetInput = document.getElementById('thinkingBudget');
    const temperatureInput = document.getElementById('temperature');
    const topPInput = document.getElementById('topP');
    const topKInput = document.getElementById('topK');
    const streamingCheckbox = document.getElementById('streaming');
    const thinkingCheckbox = document.getElementById('thinking');
    const descriptionInput = document.getElementById('description');

    const tmdbInfoDiv = document.getElementById('tmdb-info');
    const tmdbTitleSpan = document.getElementById('tmdb-title');
    const tmdbYearSpan = document.getElementById('tmdb-year');
    const tmdbOverviewSpan = document.getElementById('tmdb-overview');
    const tmdbEpisodeTitleSpan = document.getElementById('tmdb-episode-title');
    const tmdbEpisodeOverviewSpan = document.getElementById('tmdb-episode-overview');
    const tmdbPosterImg = document.getElementById('tmdb-poster');
    const loadingIndicator = document.getElementById('loading-indicator');
    const notificationToast = new bootstrap.Toast(document.getElementById('notificationToast'));

    let currentMatches = [];

    let eventSource = null;

    function initEventSource() {
        const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
        const sseUrl = `${protocol}//${window.location.host}/logs/stream/`;
        
        eventSource = new EventSource(sseUrl);
        
        eventSource.onmessage = (event) => {
            try {
                const logData = JSON.parse(event.data);
                if (logData.type === 'log') {
                    logToConsole(logData.message, logData.level);
                } else if (logData.type === 'progress' || logData.type === 'translation_progress') {
                    updateProgressBarFromData(logData);
                } else {
                    logToConsole(event.data, 'info');
                }
            } catch (e) {
                logToConsole(event.data, 'error');
            }
        };
        
        eventSource.onopen = () => {
            console.log('SSE connection opened.');
            logToConsole('Connected to server for real-time updates.', 'success');
        };

        eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            logToConsole('Connection to server lost. Please refresh the page.', 'error');
            eventSource.close();
        };
    }

    function updateProgressBarFromData(logData) {
        const progressBar = document.getElementById('translationProgress');
        const progressText = document.getElementById('progressText');
        const currentFile = document.getElementById('currentFile');
        const progressContainer = document.getElementById('progressContainer');
        
        // Make sure the progress container is visible
        if (progressContainer) {
            progressContainer.style.display = 'block';
        }
        
        if (logData.type === 'progress') {
            const progress = logData.total > 0 ? Math.round((logData.current / logData.total) * 100) : 0;
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
                progressBar.setAttribute('aria-valuenow', progress);
                progressBar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
                progressBar.classList.add('bg-info');
            }
            if (progressText) {
                progressText.textContent = `${progress}% - ${logData.current || 0}/${logData.total || 0} files`;
            }
            if (currentFile) {
                currentFile.textContent = logData.filename || logData.message || '';
            }
        } else if (logData.type === 'translation_progress') {
            const progress = logData.total_chunks > 0 ? Math.round((logData.current_chunk / logData.total_chunks) * 100) : 0;
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
                progressBar.setAttribute('aria-valuenow', progress);
                progressBar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
                progressBar.classList.add('bg-info');
            }
            if (progressText) {
                progressText.textContent = `${progress}% - File ${logData.current_file || 1}/${logData.total_files || 1}`;
            }
            if (currentFile) {
                currentFile.textContent = logData.filename || 'Processing...';
            }
        } else if (logData.type === 'log') {
            if (logData.level === 'error') {
                // Handle error state
                if (progressBar) {
                    progressBar.classList.remove('bg-info', 'bg-warning');
                    progressBar.classList.add('bg-danger');
                }
                if (progressText) {
                    progressText.textContent = 'Error: ' + (logData.message || 'An error occurred');
                }
            } else if (logData.level === 'warning') {
                // Handle warning state
                if (progressBar) {
                    progressBar.classList.remove('bg-info', 'bg-danger');
                    progressBar.classList.add('bg-warning');
                }
            } else if (logData.level === 'success') {
                // Handle success state
                if (progressBar) {
                    progressBar.classList.remove('bg-info', 'bg-warning', 'bg-danger');
                    progressBar.classList.add('bg-success');
                }
                if (progressText) {
                    progressText.textContent = 'Translation complete!';
                }
            }
        }
    }

    function showLoading() {
        loadingIndicator.classList.remove('d-none');
    }

    function hideLoading() {
        loadingIndicator.classList.add('d-none');
    }

    function showNotification(message, isError = false) {
        const toastBody = notificationToast._element.querySelector('.toast-body');
        toastBody.textContent = message;
        if (isError) {
            notificationToast._element.classList.remove('bg-success');
            notificationToast._element.classList.add('bg-danger', 'text-white');
        } else {
            notificationToast._element.classList.remove('bg-danger', 'text-white');
            notificationToast._element.classList.add('bg-success', 'text-white');
        }
        notificationToast.show();
    }

    function logToConsole(message, level = 'info') {
        const p = document.createElement('p');
        const icon = document.createElement('i');
        
        p.classList.add(`log-${level}`);
        icon.classList.add('fas', 'me-2');

        switch (level) {
            case 'success':
                icon.classList.add('fa-check-circle');
                break;
            case 'warning':
                icon.classList.add('fa-exclamation-triangle');
                break;
            case 'error':
                icon.classList.add('fa-times-circle');
                break;
            case 'info':
            default:
                icon.classList.add('fa-info-circle');
                break;
        }
        
        p.appendChild(icon);
        const messageNode = document.createElement('span');
        messageNode.innerHTML = message;
        p.appendChild(messageNode);
        
        consoleOutput.appendChild(p);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.add('highlight'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.remove('highlight'), false);
    });

    dropArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
    dropArea.addEventListener('drop', (e) => handleFiles(e.dataTransfer.files), false);

    async function handleFiles(files) {
        if (files.length === 0) return;

        noFilesMessage.style.display = 'none';
        const formData = new FormData();
        for (const file of files) {
            formData.append('files', file);
        }

        logToConsole(`Uploading ${files.length} files...`);
        showLoading();

        try {
            const response = await fetch('/upload_files/', {
                method: 'POST',
                body: formData,
            });

            if (response.ok) {
                currentMatches = await response.json();
                displayFileMatches(currentMatches);
                logToConsole(`Successfully processed ${files.length} files.`, 'success');
                showNotification('Files uploaded and processed successfully!');
            } else {
                const errorData = await response.json();
                const errorMessage = `Error processing files: ${errorData.detail || response.statusText}`;
                logToConsole(errorMessage, 'error');
                showNotification(errorMessage, true);
            }
        } catch (error) {
            const errorMessage = `Network error processing files: ${error.message}`;
            logToConsole(errorMessage, 'error');
            showNotification(errorMessage, true);
        } finally {
            hideLoading();
        }
    }

    function displayFileMatches(matches) {
        fileListBody.innerHTML = '';
        if (matches.length === 0) {
            noFilesMessage.style.display = 'block';
            return;
        }

        matches.forEach((match, index) => {
            const row = fileListBody.insertRow();
            row.dataset.index = index;
            row.dataset.filename = match.subtitle ? match.subtitle.split('/').pop() : '-';

            // Checkbox
            const checkboxCell = row.insertCell();
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'form-check-input';
            checkbox.checked = true;
            checkboxCell.appendChild(checkbox);

            // Subtitle File
            const subtitleCell = row.insertCell();
            subtitleCell.innerHTML = `<i class="fas fa-closed-captioning me-2"></i> ${row.dataset.filename}`;

            // Video File
            const videoCell = row.insertCell();
            videoCell.innerHTML = match.video ? `<i class="fas fa-video me-2"></i> ${match.video.split('/').pop()}` : '-';

            // Status
            const statusCell = row.insertCell();
            statusCell.innerHTML = `<span class="badge bg-secondary">Ready</span>`;

            // Action
            const actionCell = row.insertCell();
            actionCell.innerHTML = '';
        });
    }
    
    function updateFileStatusByName(filename, status, badgeClass) {
        const row = fileListBody.querySelector(`tr[data-filename="${filename}"]`);
        if (row) {
            const statusCell = row.cells[3];
            statusCell.innerHTML = `<span class="badge ${badgeClass}">${status}</span>`;
        }
    }

    selectAllCheckbox.addEventListener('change', () => {
        const checkboxes = fileListBody.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = selectAllCheckbox.checked;
        });
    });

    async function loadConfig() {
        try {
            const response = await fetch('/config/');
            if (response.ok) {
                const config = await response.json();
                geminiApiKeyInput.value = config.gemini_api_key || '';
                tmdbApiKeyInput.value = config.tmdb_api_key || '';
                languageInput.value = config.language || '';
                languageCodeInput.value = config.language_code || '';
                extractAudioCheckbox.checked = config.extract_audio !== false;
                autoFetchTmdbCheckbox.checked = config.auto_fetch_tmdb !== false;
                isTvSeriesCheckbox.checked = config.is_tv_series || false;
                seriesTitleInput.value = config.series_title || '';
                addTranslatorInfoCheckbox.checked = config.add_translator_info !== false;

                // Populate new fields
                geminiApiKey2Input.value = config.gemini_api_key2 || '';
                batchSizeInput.value = config.batch_size !== undefined ? config.batch_size : 50;
                thinkingBudgetInput.value = config.thinking_budget !== undefined ? config.thinking_budget : 0;
                temperatureInput.value = config.temperature !== undefined ? config.temperature : 0.2;
                topPInput.value = config.top_p !== undefined ? config.top_p : 0.8;
                topKInput.value = config.top_k !== undefined ? config.top_k : 40;
                streamingCheckbox.checked = config.streaming !== false; // Default to true if not set
                thinkingCheckbox.checked = config.thinking || false; // Default to false if not set
                descriptionInput.value = config.description || '';

                if (config.language && config.language_code) {
                    const option = Array.from(languageSelect.options).find(
                        opt => opt.value === `${config.language}|${config.language_code}`
                    );
                    if (option) languageSelect.value = option.value;
                }

                await loadModels(config.model);
            } else {
                logToConsole('Failed to load config', 'error');
            }
        } catch (error) {
            logToConsole(`Error loading config: ${error.message}`, 'error');
        }
    }

    async function loadModels(selectedModel) {
        try {
            const response = await fetch('/models/');
            if (response.ok) {
                const models = await response.json();
                modelSelect.innerHTML = '';
                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    if (model === selectedModel) {
                        option.selected = true;
                    }
                    modelSelect.appendChild(option);
                });
            } else {
                logToConsole('Error loading models.', 'error');
            }
        } catch (error) {
            logToConsole(`Network error loading models: ${error.message}`, 'error');
        }
    }

    const languageSelect = document.getElementById('languageSelect');
    languageSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            const [language, code] = e.target.value.split('|');
            languageInput.value = language;
            languageCodeInput.value = code;
        } else {
            languageInput.value = '';
            languageCodeInput.value = '';
        }
    });

    saveConfigBtn.addEventListener('click', async () => {
        const config = {
            gemini_api_key: geminiApiKeyInput.value,
            gemini_api_key2: geminiApiKey2Input.value,
            model: modelSelect.value,
            tmdb_api_key: tmdbApiKeyInput.value,
            language: languageInput.value,
            language_code: languageCodeInput.value,
            extract_audio: extractAudioCheckbox.checked,
            auto_fetch_tmdb: autoFetchTmdbCheckbox.checked,
            is_tv_series: isTvSeriesCheckbox.checked,
            add_translator_info: addTranslatorInfoCheckbox.checked,
            series_title: seriesTitleInput.value,
            batch_size: parseInt(batchSizeInput.value) || 50,
            streaming: streamingCheckbox.checked,
            thinking: thinkingCheckbox.checked,
            thinking_budget: parseInt(thinkingBudgetInput.value) || 0,
            temperature: parseFloat(temperatureInput.value) || 0.2,
            top_p: parseFloat(topPInput.value) || 0.8,
            top_k: parseInt(topKInput.value) || 40,
            description: descriptionInput.value
        };

        try {
            const response = await fetch('/config/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            if (response.ok) {
                showNotification('Configuration saved successfully!');
            } else {
                throw new Error('Failed to save configuration');
            }
        } catch (error) {
            showNotification(`Error saving configuration: ${error.message}`, true);
            showNotification(errorMessage, true);
        } finally {
            hideLoading();
        }
    });

    isTvSeriesCheckbox.addEventListener('change', () => {
        seriesTitleContainer.style.display = isTvSeriesCheckbox.checked ? 'block' : 'none';
    });

    fetchTmdbBtn.addEventListener('click', async () => {
        if (currentMatches.length === 0) {
            showNotification("No files detected to fetch TMDB info for.", true);
            return;
        }

        const firstFile = currentMatches[0];
        const filename = firstFile.subtitle ? firstFile.subtitle.split('/').pop() : firstFile.video.split('/').pop();
        const isTvSeries = isTvSeriesCheckbox.checked;
        let seriesTitle = seriesTitleInput.value.trim();

        logToConsole(`Fetching TMDB info for: ${filename}...`);
        showLoading();

        try {
            const params = new URLSearchParams({ filename, is_tv_series: isTvSeries });
            if (isTvSeries && seriesTitle) {
                params.append('series_title', seriesTitle);
            }

            const response = await fetch(`/tmdb/info?${params.toString()}`);

            if (response.ok) {
                const tmdbInfo = await response.json();
                if (tmdbInfo && tmdbInfo.title) {
                    tmdbInfoDiv.style.display = 'block';
                    tmdbTitleSpan.textContent = tmdbInfo.title || 'N/A';
                    tmdbYearSpan.textContent = tmdbInfo.year || 'N/A';
                    tmdbOverviewSpan.textContent = tmdbInfo.overview || 'N/A';
                    tmdbEpisodeTitleSpan.textContent = tmdbInfo.episode_title || 'N/A';
                    tmdbEpisodeOverviewSpan.textContent = tmdbInfo.episode_overview || 'N/A';

                    if (tmdbInfo.poster_path) {
                        tmdbPosterImg.src = `https://image.tmdb.org/t/p/w300${tmdbInfo.poster_path}`;
                        tmdbPosterImg.style.display = 'block';
                    } else {
                        tmdbPosterImg.style.display = 'none';
                    }
                    logToConsole(`TMDB Info fetched for: ${tmdbInfo.title}`, 'success');
                    showNotification('TMDB info fetched successfully!');
                } else {
                    tmdbInfoDiv.style.display = 'none';
                    logToConsole("No TMDB info found for this file.", 'warning');
                    showNotification('No TMDB info found.', true);
                }
            } else {
                const errorData = await response.json();
                const errorMessage = `Error fetching TMDB info: ${errorData.detail || response.statusText}`;
                logToConsole(errorMessage, 'error');
                showNotification(errorMessage, true);
            }
        } catch (error) {
            const errorMessage = `Network error fetching TMDB info: ${error.message}`;
            logToConsole(errorMessage, 'error');
            showNotification(errorMessage, true);
        } finally {
            hideLoading();
        }
    });

    translateBtn.addEventListener('click', async () => {
        const selectedFiles = [];
        const selectedIndices = [];
        
        fileListBody.querySelectorAll('input[type="checkbox"]:checked').forEach(checkbox => {
            const row = checkbox.closest('tr');
            const rowIndex = row.dataset.index;
            selectedFiles.push(currentMatches[rowIndex]);
            selectedIndices.push(rowIndex);
        });

        if (selectedFiles.length === 0) {
            showNotification("No files selected for translation.", true);
            return;
        }

        logToConsole(`Initiating translation for ${selectedFiles.length} file(s)...`);
        showLoading();
        document.getElementById('progressContainer').style.display = 'block';
        document.getElementById('currentFile').textContent = '';
        updateProgressBarFromData({type: 'progress', current: 0, total: selectedFiles.length, filename: ''});

        try {
            // Create the request data with selected_files as the main array
            // and other parameters as top-level properties
            const requestData = {
                selected_files: selectedFiles.map(file => ({
                    subtitle: file.subtitle,
                    video: file.video,
                    status: file.status || 'pending'
                })),
                gemini_api_key2: geminiApiKey2Input.value || undefined,
                batch_size: parseInt(batchSizeInput.value) || undefined,
                temperature: parseFloat(temperatureInput.value) || undefined,
                top_p: parseFloat(topPInput.value) || undefined,
                top_k: parseInt(topKInput.value) || undefined,
                streaming: streamingCheckbox.checked || undefined,
                thinking: thinkingCheckbox.checked || undefined,
                thinking_budget: parseInt(thinkingBudgetInput.value) || undefined,
                description: descriptionInput.value || undefined
            };
            
            // Remove undefined values to avoid sending them
            Object.keys(requestData).forEach(key => {
                if (requestData[key] === undefined) {
                    delete requestData[key];
                }
            });
            
            console.log('Sending request data:', JSON.stringify(requestData, null, 2));

            // Send the request with the prepared data
            const response = await fetch('/translate/', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error('Server error response:', errorData);
                throw new Error(`Server responded with status ${response.status}: ${JSON.stringify(errorData.detail || errorData) || response.statusText}`);
            }

            if (response.ok) {
                const results = await response.json();
                logToConsole("<strong>Translation Results:</strong>", 'success');
                
                results.forEach((result, i) => {
                    const originalName = result.original_subtitle ? result.original_subtitle.split('/').pop() : 'Unknown';
                    const translatedName = result.translated_subtitle ? result.translated_subtitle.split('/').pop() : 'N/A';
                    
                    const originalIndex = selectedIndices[i];
                    const row = fileListBody.querySelector(`tr[data-index='${originalIndex}']`);

                    if (result.status === 'Success') {
                        updateFileStatusByName(originalName, 'Complete', 'bg-success');
                        const actionCell = row.cells[4];
                        const downloadBtn = document.createElement('a');
                        downloadBtn.href = `/download/${translatedName}`;
                        downloadBtn.className = 'btn btn-sm btn-success';
                        downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download';
                        actionCell.innerHTML = ''; // Clear previous content
                        actionCell.appendChild(downloadBtn);
                    } else {
                        updateFileStatusByName(originalName, 'Failed', 'bg-danger');
                    }

                    logToConsole(`- <strong>${originalName}</strong> -> ${translatedName} <span class="badge bg-${result.status === 'Success' ? 'success' : 'danger'}">${result.status}</span>`, 'info');
                });
                
                showNotification("Translation completed successfully!");
            } else {
                const error = await response.text();
                throw new Error(`Server responded with status ${response.status}: ${error}`);
            }
        } catch (error) {
            logToConsole(`Translation error: ${error.message}`, 'error');
            showNotification(`Translation failed: ${error.message}`, true);
        } finally {
            hideLoading();
            setTimeout(() => {
                document.getElementById('progressContainer').style.display = 'none';
            }, 2000);
        }
    });

    // Initial load
    initEventSource();
    loadConfig();
    logToConsole("Web GUI loaded. Drag and drop files to start.");

    const clearCacheBtn = document.getElementById('clearCacheBtn');
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/clear_cache', { method: 'POST' });
                const result = await response.json();
                if (result.status === 'success') {
                    showNotification('Translation cache cleared successfully!');
                    logToConsole('Translation cache cleared.', 'success');
                } else {
                    throw new Error(result.message || 'Failed to clear cache');
                }
            } catch (error) {
                logToConsole(`Error clearing cache: ${error.message}`, 'error');
                showNotification(`Failed to clear cache: ${error.message}`, true);
            }
        });
    }
});