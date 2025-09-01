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

    function logToConsole(message) {
        const p = document.createElement('p');
        p.innerHTML = message; // Use innerHTML to render potential HTML tags
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
                logToConsole(`Successfully processed ${files.length} files.`);
                showNotification('Files uploaded and processed successfully!');
            } else {
                const errorData = await response.json();
                const errorMessage = `Error processing files: ${errorData.detail || response.statusText}`;
                logToConsole(errorMessage);
                showNotification(errorMessage, true);
            }
        } catch (error) {
            const errorMessage = `Network error processing files: ${error.message}`;
            logToConsole(errorMessage);
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
            const row = fileListBody.insertRow(index); // Set the index here
            row.dataset.index = index;
            row.classList.add('file-item-row');

            const checkboxCell = row.insertCell();
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'form-check-input';
            checkbox.checked = true;
            checkboxCell.appendChild(checkbox);

            const subtitleCell = row.insertCell();
            subtitleCell.textContent = match.subtitle ? match.subtitle.split('/').pop() : '-';

            const videoCell = row.insertCell();
            videoCell.textContent = match.video ? match.video.split('/').pop() : '-';

            const statusCell = row.insertCell();
            statusCell.innerHTML = `<span class="badge bg-secondary">${match.status || 'Matched'}</span>`;

            const actionCell = row.insertCell(); // Create a cell for actions
            actionCell.innerHTML = ''; // Initially empty

            row.addEventListener('click', (e) => {
                if (e.target.type !== 'checkbox' && !e.target.closest('a')) { // Also check if the click is not on a link
                    checkbox.checked = !checkbox.checked;
                }
                row.classList.toggle('table-active', checkbox.checked);
            });
            row.classList.toggle('table-active', checkbox.checked);
        });
    }

    selectAllCheckbox.addEventListener('change', () => {
        const checkboxes = fileListBody.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = selectAllCheckbox.checked;
            checkbox.closest('tr').classList.toggle('table-active', checkbox.checked);
        });
    });

    async function loadConfig() {
        try {
            const response = await fetch('/config/');
            if (response.ok) {
                const config = await response.json();
                geminiApiKeyInput.value = config.gemini_api_key || '';
                tmdbApiKeyInput.value = config.tmdb_api_key || '';
                languageInput.value = config.language || 'English';
                languageCodeInput.value = config.language_code || 'en';
                extractAudioCheckbox.checked = config.extract_audio || false;
                autoFetchTmdbCheckbox.checked = config.auto_fetch_tmdb || false;
                isTvSeriesCheckbox.checked = config.is_tv_series || false;
                addTranslatorInfoCheckbox.checked = config.add_translator_info || false;
                seriesTitleInput.value = config.series_title || '';
                seriesTitleContainer.style.display = isTvSeriesCheckbox.checked ? 'block' : 'none';

                // Load models and set selected
                await loadModels(config.model);

                logToConsole("Configuration loaded.");
            } else {
                logToConsole("Error loading configuration.");
                await loadModels(); // Still try to load models
            }
        } catch (error) {
            logToConsole(`Network error loading configuration: ${error.message}`);
            await loadModels(); // Still try to load models
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
                logToConsole('Error loading models.');
            }
        } catch (error) {
            logToConsole(`Network error loading models: ${error.message}`);
        }
    }

    saveConfigBtn.addEventListener('click', async () => {
        const config = {
            gemini_api_key: geminiApiKeyInput.value,
            model: modelSelect.value,
            tmdb_api_key: tmdbApiKeyInput.value,
            language: languageInput.value,
            language_code: languageCodeInput.value,
            extract_audio: extractAudioCheckbox.checked,
            auto_fetch_tmdb: autoFetchTmdbCheckbox.checked,
            is_tv_series: isTvSeriesCheckbox.checked,
            series_title: seriesTitleInput.value,
            add_translator_info: addTranslatorInfoCheckbox.checked,
        };

        showLoading();
        try {
            const response = await fetch('/config/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });

            if (response.ok) {
                logToConsole("Configuration saved successfully!");
                showNotification('Configuration saved!');
            } else {
                const errorData = await response.json();
                const errorMessage = `Error saving configuration: ${errorData.detail || response.statusText}`;
                logToConsole(errorMessage);
                showNotification(errorMessage, true);
            }
        } catch (error) {
            const errorMessage = `Network error saving configuration: ${error.message}`;
            logToConsole(errorMessage);
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
            const params = new URLSearchParams({
                filename,
                is_tv_series: isTvSeries,
            });
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
                    logToConsole(`TMDB Info fetched for: ${tmdbInfo.title}`);
                    showNotification('TMDB info fetched successfully!');
                } else {
                    tmdbInfoDiv.style.display = 'none';
                    logToConsole("No TMDB info found for this file.");
                    showNotification('No TMDB info found.', true);
                }
            } else {
                const errorData = await response.json();
                const errorMessage = `Error fetching TMDB info: ${errorData.detail || response.statusText}`;
                logToConsole(errorMessage);
                showNotification(errorMessage, true);
                tmdbInfoDiv.style.display = 'none';
            }
        } catch (error) {
            const errorMessage = `Network error fetching TMDB info: ${error.message}`;
            logToConsole(errorMessage);
            showNotification(errorMessage, true);
            tmdbInfoDiv.style.display = 'none';
        } finally {
            hideLoading();
        }
    });

    translateBtn.addEventListener('click', async () => {
        console.log('Translate button clicked.');

        const selectedFiles = [];
        const selectedIndices = []; // Keep track of original indices
        fileListBody.querySelectorAll('input[type="checkbox"]:checked').forEach(checkbox => {
            const rowIndex = checkbox.closest('tr').dataset.index;
            selectedFiles.push(currentMatches[rowIndex]);
            selectedIndices.push(rowIndex); // Store the index
        });

        if (selectedFiles.length === 0) {
            showNotification("No files selected for translation.", true);
            return;
        }

        logToConsole(`Initiating translation for ${selectedFiles.length} file(s)...`);
        showLoading();

        try {
            console.log('Sending translation request for:', selectedFiles);
            const response = await fetch('/translate/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(selectedFiles),
            });

            console.log('Received translation response:', response);

            if (response.ok) {
                const results = await response.json();
                logToConsole("<strong>Translation Results:</strong>");
                console.log('Translation results received:', results);
                results.forEach((result, i) => { // Use the loop index 'i' to get the original row index
                    const originalName = result.original_subtitle.split('/').pop();
                    const translatedName = result.translated_subtitle ? result.translated_subtitle.split('/').pop() : 'N/A';
                    const statusBadge = result.status === 'Success' ? 'bg-success' : 'bg-danger';
                    logToConsole(`- <strong>${originalName}</strong> -> ${translatedName} <span class="badge ${statusBadge}">${result.status}</span>`);

                    // Find the row using the stored index
                    const originalIndex = selectedIndices[i];
                    const row = fileListBody.querySelector(`tr[data-index='${originalIndex}']`);
                    console.log(`Processing result ${i}: originalIndex=${originalIndex}, row found:`, row);

                    if (row) {
                        row.cells[3].innerHTML = `<span class="badge ${statusBadge}">${result.status}</span>`;
                        if (result.status === 'Success' && result.translated_subtitle) {
                            const translatedName = result.translated_subtitle.split('/').pop();
                            console.log(`Adding download button for ${translatedName} to row`, row);
                            row.cells[4].innerHTML = `<a href="/download/${translatedName}" class="btn btn-sm btn-outline-success" download><i class="fas fa-download"></i> Download</a>`;
                        } else {
                            console.log('Translation not successful or no translated_subtitle path.');
                        }
                    }
                });
                showNotification('Translation process completed!');
            } else {
                const errorData = await response.json();
                const errorMessage = `Error during translation: ${errorData.detail || response.statusText}`;
                console.error('Translation failed with error response:', errorMessage, errorData);
                logToConsole(errorMessage);
                showNotification(errorMessage, true);
            }
        } catch (error) {
            const errorMessage = `Network error during translation: ${error.message}`;
            console.error('A network error occurred during translation:', errorMessage, error);
            logToConsole(errorMessage);
            showNotification(errorMessage, true);
        } finally {
            hideLoading();
        }
    });

    // Initial load
    loadConfig();
    logToConsole("Web GUI loaded. Drag and drop files to start.");
});