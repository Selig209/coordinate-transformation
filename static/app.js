// API Base URL
const API_URL = 'http://localhost:5000/api';

// Global variables
let map;
let markers = [];
let batchData = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    loadCRSInfo();
});

// Tab switching
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    event.target.classList.add('active');
}

// Initialize Leaflet map
function initializeMap() {
    // Center on Ghana
    map = L.map('map').setView([7.9465, -1.0232], 7);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    // Add Ghana boundary outline (approximate)
    const ghanaBounds = [
        [11.1667, -3.2500],
        [11.1667, 1.2000],
        [4.7333, 1.2000],
        [4.7333, -3.2500],
        [11.1667, -3.2500]
    ];

    L.polyline(ghanaBounds, {
        color: '#2563eb',
        weight: 2,
        opacity: 0.5,
        dashArray: '5, 10'
    }).addTo(map);
}

// Update input labels based on selected CRS
function updateInputLabels() {
    const sourceCRS = document.getElementById('source-crs').value;
    const xLabel = document.getElementById('input-x-label');
    const yLabel = document.getElementById('input-y-label');
    const xInput = document.getElementById('input-x');
    const yInput = document.getElementById('input-y');

    if (sourceCRS === 'WGS84') {
        xLabel.textContent = 'Longitude';
        yLabel.textContent = 'Latitude';
        xInput.placeholder = '-0.1870';
        yInput.placeholder = '5.6037';
    } else {
        xLabel.textContent = 'Easting (X)';
        yLabel.textContent = 'Northing (Y)';
        xInput.placeholder = '829884.5';
        yInput.placeholder = '620614.0';
    }
}

// Set quick location
function setLocation(lon, lat) {
    document.getElementById('input-x').value = lon;
    document.getElementById('input-y').value = lat;
}

// Transform coordinates
async function transformCoordinates() {
    const sourceCRS = document.getElementById('source-crs').value;
    const targetCRS = document.getElementById('target-crs').value;
    const x = parseFloat(document.getElementById('input-x').value);
    const y = parseFloat(document.getElementById('input-y').value);

    if (isNaN(x) || isNaN(y)) {
        showError('Please enter valid coordinate values');
        return;
    }

    // Prepare request
    const requestData = {
        source_crs: sourceCRS,
        target_crs: targetCRS,
        coordinates: sourceCRS === 'WGS84' ? { lon: x, lat: y } : { x: x, y: y }
    };

    try {
        const response = await fetch(`${API_URL}/transform`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            throw new Error('Transformation failed');
        }

        const result = await response.json();
        displayResults(result);
        updateMap(result);
        
        // Show accuracy card
        document.getElementById('accuracy-card').style.display = 'block';
        displayAccuracy(result.accuracy, result.metadata);

    } catch (error) {
        showError('Error: ' + error.message);
    }
}

// Display transformation results
function displayResults(result) {
    const container = document.getElementById('results-container');
    
    const sourceCRS = result.source.crs;
    const targetCRS = result.target.crs;
    
    let html = `
        <div class="results-display">
            <h3>Source Coordinates (${sourceCRS})</h3>
            <div class="result-item">
                <span class="result-label">${sourceCRS === 'WGS84' ? 'Longitude' : 'Easting (X)'}</span>
                <span class="result-value">${result.source.x.toFixed(6)}</span>
            </div>
            <div class="result-item">
                <span class="result-label">${sourceCRS === 'WGS84' ? 'Latitude' : 'Northing (Y)'}</span>
                <span class="result-value">${result.source.y.toFixed(6)}</span>
            </div>

            <h3 style="margin-top: 20px;">Transformed Coordinates (${targetCRS})</h3>
            <div class="result-item">
                <span class="result-label">${targetCRS === 'WGS84' ? 'Longitude' : 'Easting (X)'}</span>
                <span class="result-value">${result.target.x.toFixed(6)}
                    <button class="copy-btn" onclick="copyToClipboard('${result.target.x}')">
                        <i class="fas fa-copy"></i>
                    </button>
                </span>
            </div>
            <div class="result-item">
                <span class="result-label">${targetCRS === 'WGS84' ? 'Latitude' : 'Northing (Y)'}</span>
                <span class="result-value">${result.target.y.toFixed(6)}
                    <button class="copy-btn" onclick="copyToClipboard('${result.target.y}')">
                        <i class="fas fa-copy"></i>
                    </button>
                </span>
            </div>
        </div>
    `;

    // Add metadata if available
    if (result.metadata) {
        html += `
            <div class="metadata-section">
                <h4><i class="fas fa-info-circle"></i> Additional Information</h4>
                <div class="result-item">
                    <span class="result-label">UTM Zone</span>
                    <span class="result-value">${result.metadata.zone}</span>
                </div>
                <div class="result-item">
                    <span class="result-label">Grid Convergence</span>
                    <span class="result-value">${result.metadata.convergence.toFixed(6)}°</span>
                </div>
                <div class="result-item">
                    <span class="result-label">Point Scale Factor</span>
                    <span class="result-value">${result.metadata.scale_factor.toFixed(8)}</span>
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
}

// Display accuracy information
function displayAccuracy(accuracy, metadata) {
    const container = document.getElementById('accuracy-info');
    
    let html = `
        <div class="accuracy-info">
            <h4><i class="fas fa-bullseye"></i> Expected Accuracy: ${accuracy.accuracy}</h4>
            <div class="accuracy-detail">
                <strong>Description:</strong> ${accuracy.description}
            </div>
            <div class="accuracy-detail">
                <strong>Typical Use Cases:</strong> ${accuracy.use_case}
            </div>
        </div>
    `;
    
    container.innerHTML = html;
}

// Update map with markers
function updateMap(result) {
    // Clear existing markers
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    // Determine which coordinates to display on map (always convert to WGS84 for display)
    let lat, lon;

    if (result.source.crs === 'WGS84') {
        lon = result.source.x;
        lat = result.source.y;
    } else if (result.target.crs === 'WGS84') {
        lon = result.target.x;
        lat = result.target.y;
    } else {
        // If neither is WGS84, we'll need to convert for display
        // For now, skip map update
        return;
    }

    // Add marker
    const marker = L.marker([lat, lon]).addTo(map);
    marker.bindPopup(`
        <strong>Location</strong><br>
        Lat: ${lat.toFixed(6)}<br>
        Lon: ${lon.toFixed(6)}
    `).openPopup();
    
    markers.push(marker);

    // Center map on marker
    map.setView([lat, lon], 12);
}

// Load CRS information
async function loadCRSInfo() {
    try {
        const response = await fetch(`${API_URL}/crs-info`);
        const crsInfo = await response.json();
        displayCRSInfo(crsInfo);
    } catch (error) {
        console.error('Error loading CRS info:', error);
    }
}

// Display CRS information
function displayCRSInfo(crsInfo) {
    const container = document.getElementById('crs-info-container');
    
    let html = '<div class="crs-grid">';
    
    for (const [key, info] of Object.entries(crsInfo)) {
        html += `
            <div class="crs-card">
                <h3>${info.name}</h3>
                <div class="crs-detail"><strong>Type:</strong> ${info.type}</div>
                <div class="crs-detail"><strong>Units:</strong> ${info.units}</div>
                ${info.epsg ? `<div class="crs-detail"><strong>EPSG:</strong> ${info.epsg}</div>` : ''}
                ${info.datum ? `<div class="crs-detail"><strong>Datum:</strong> ${info.datum}</div>` : ''}
                ${info.projection ? `<div class="crs-detail"><strong>Projection:</strong> ${info.projection}</div>` : ''}
                <div class="crs-detail" style="margin-top: 10px;">${info.description}</div>
            </div>
        `;
    }
    
    html += '</div>';
    container.innerHTML = html;
}

// Handle file selection
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        document.getElementById('file-info').textContent = file.name;
        document.getElementById('process-batch-btn').disabled = false;
    }
}

// Process batch transformation
async function processBatch() {
    const file = document.getElementById('csv-file').files[0];
    const sourceCRS = document.getElementById('batch-source-crs').value;
    const targetCRS = document.getElementById('batch-target-crs').value;

    if (!file) {
        showError('Please select a CSV file');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_crs', sourceCRS);
    formData.append('target_crs', targetCRS);

    try {
        const response = await fetch(`${API_URL}/transform-batch`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Batch processing failed');
        }

        const result = await response.json();
        batchData = result.data;
        displayBatchResults(result);

    } catch (error) {
        showError('Error: ' + error.message);
    }
}

// Display batch results
function displayBatchResults(result) {
    const resultsDiv = document.getElementById('batch-results');
    const statsDiv = document.getElementById('batch-stats');
    const previewDiv = document.getElementById('results-preview');

    // Show results section
    resultsDiv.style.display = 'block';

    // Display stats
    let statsHTML = `
        <div class="stat-row">
            <strong>Total Coordinates Processed:</strong>
            <span>${result.total_processed}</span>
        </div>
    `;

    if (result.errors.length > 0) {
        statsHTML += `
            <div class="stat-row">
                <strong>Errors:</strong>
                <span style="color: var(--danger-color);">${result.errors.length}</span>
            </div>
        `;
    }

    statsDiv.innerHTML = statsHTML;

    // Display preview (first 10 rows)
    if (result.data.length > 0) {
        const preview = result.data.slice(0, 10);
        const columns = Object.keys(preview[0]);

        let tableHTML = '<table><thead><tr>';
        columns.forEach(col => {
            tableHTML += `<th>${col}</th>`;
        });
        tableHTML += '</tr></thead><tbody>';

        preview.forEach(row => {
            tableHTML += '<tr>';
            columns.forEach(col => {
                tableHTML += `<td>${row[col]}</td>`;
            });
            tableHTML += '</tr>';
        });

        tableHTML += '</tbody></table>';
        
        if (result.data.length > 10) {
            tableHTML += `<p style="margin-top: 10px; color: var(--text-muted);">Showing 10 of ${result.data.length} rows</p>`;
        }

        previewDiv.innerHTML = tableHTML;
    }
}

// Download transformed results
function downloadResults() {
    if (!batchData || batchData.length === 0) {
        showError('No data to download');
        return;
    }

    // Convert to CSV
    const columns = Object.keys(batchData[0]);
    let csv = columns.join(',') + '\n';

    batchData.forEach(row => {
        const values = columns.map(col => row[col]);
        csv += values.join(',') + '\n';
    });

    // Create download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transformed_coordinates.csv';
    a.click();
    window.URL.revokeObjectURL(url);
}

// Download sample CSV
function downloadSampleCSV() {
    const sampleData = `lon,lat,location
-0.1870,5.6037,Accra
-1.6163,6.6885,Kumasi
-0.0300,9.4034,Tamale
-2.3333,4.9000,Takoradi
-0.9000,5.5500,Cape Coast`;

    const blob = new Blob([sampleData], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample_coordinates.csv';
    a.click();
    window.URL.revokeObjectURL(url);
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Show brief success message
        const btn = event.target.closest('.copy-btn');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check"></i>';
        setTimeout(() => {
            btn.innerHTML = originalHTML;
        }, 2000);
    });
}

// Show error message
function showError(message) {
    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = `
        <div class="alert alert-error">
            <i class="fas fa-exclamation-circle"></i> ${message}
        </div>
    `;
}
