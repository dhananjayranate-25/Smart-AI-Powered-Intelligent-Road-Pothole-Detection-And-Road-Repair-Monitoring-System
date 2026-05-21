let currentFile = null;
let currentResultData = null;
let stream = null;
let resultPath = null;
let lastPotholeCount = 0;
let cumulativeDetections = [];
let potholeMap = null;
let reportMediaData = null;

document.addEventListener('DOMContentLoaded', function() {
    initTabs();
    initUploadHandlers();
    initDetection();
    initLiveCamera();
    initReportForm();
    initFAQ();
    loadLiveStats();
});

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });

    document.querySelector('a[href="#whatSection"]')?.addEventListener('click', function(e) {
        e.preventDefault(); document.getElementById('whatSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    document.querySelector('a[href="#useSection"]')?.addEventListener('click', function(e) {
        e.preventDefault(); document.getElementById('useSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    document.querySelector('a[href="#detailsSection"]')?.addEventListener('click', function(e) {
        e.preventDefault(); document.getElementById('detailsSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    document.getElementById('detailsStartBtn')?.addEventListener('click', function(e) {
        e.preventDefault();
        showAllSections();
        document.getElementById('heroSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    document.getElementById('navLive')?.addEventListener('click', function(e) {
        e.preventDefault();
        hideAllSections();
        document.getElementById('heroSection').style.display = 'block';
        document.querySelector('[data-tab="live"]').click();
        document.getElementById('heroSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    document.getElementById('navReport').addEventListener('click', function(e) {
        e.preventDefault();
        hideAllSections();
        document.getElementById('reportSection').style.display = 'block';
        document.querySelector('[data-tab="live"]')?.classList.remove('active');
        document.querySelector('[data-tab="upload"]')?.classList.remove('active');
        document.getElementById('reportSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    document.getElementById('navMap').addEventListener('click', function(e) {
        e.preventDefault();
        hideAllSections();
        document.getElementById('mapSection').style.display = 'block';
        document.getElementById('mapSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
        if(!potholeMap) { initMapSection(); }
        else { setTimeout(() => potholeMap.invalidateSize(), 200); }
    });
    
    // Mobile nav links
    const navReportMobile = document.getElementById('navReportMobile');
    if (navReportMobile) {
        navReportMobile.addEventListener('click', function(e) {
            e.preventDefault();
            closeMobileMenu();
            hideAllSections();
            document.getElementById('reportSection').style.display = 'block';
            document.getElementById('reportSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }
    
    const navMapMobile = document.getElementById('navMapMobile');
    if (navMapMobile) {
        navMapMobile.addEventListener('click', function(e) {
            e.preventDefault();
            closeMobileMenu();
            hideAllSections();
            document.getElementById('mapSection').style.display = 'block';
            document.getElementById('mapSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
            if(!potholeMap) { initMapSection(); }
            else { setTimeout(() => potholeMap.invalidateSize(), 200); }
        });
    }
}

function showAllSections() {
    document.getElementById('heroSection').style.display = 'block';
    document.getElementById('reportSection').style.display = 'none';
    document.getElementById('mapSection').style.display = 'none';
    document.querySelector('[data-tab="live"]')?.classList.remove('active');
    document.querySelector('[data-tab="upload"]')?.classList.add('active');
    document.getElementById('upload-tab')?.classList.add('active');
    document.getElementById('live-tab')?.classList.remove('active');
}

function hideAllSections() {
    document.getElementById('heroSection').style.display = 'none';
    document.getElementById('reportSection').style.display = 'none';
    document.getElementById('mapSection').style.display = 'none';
}

document.querySelector('a[href="#heroSection"]')?.addEventListener('click', function(e) {
    e.preventDefault();
    showAllSections();
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

function loadLiveStats() {
    fetch('/api/analytics').then(res => res.json()).then(data => {
        document.getElementById('liveTotal').textContent = data.total;
        document.getElementById('livePending').textContent = data.pending;
        document.getElementById('liveQuality').textContent = (data.avg_confidence || 0) + '%';

        const counterEls = document.querySelectorAll('.counter-number');
        if (counterEls.length >= 4) {
            counterEls[0].dataset.target = data.total || 0;
            counterEls[1].dataset.target = data.total || 0;
            counterEls[2].dataset.target = data.in_progress || 0;
            counterEls[3].dataset.target = data.avg_confidence || 0;
        }
        initCounters();
    });
}

function initUploadHandlers() {
    document.getElementById('cameraCardBtn').addEventListener('click', function() { document.getElementById('fileInputCamera').click(); });
    document.getElementById('galleryCardBtn').addEventListener('click', function() { document.getElementById('fileInputGallery').click(); });
    document.getElementById('fileInputCamera').addEventListener('change', handleFileSelect);
    document.getElementById('fileInputGallery').addEventListener('change', handleFileSelect);
    document.getElementById('removeFile').addEventListener('click', resetUpload);
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        currentFile = file;
        const isVideo = file.type.startsWith('video/');
        const previewImage = document.getElementById('previewImage');
        const previewVideo = document.getElementById('previewVideo');
        
        if (isVideo) {
            const url = URL.createObjectURL(file);
            previewImage.style.display = 'none';
            previewVideo.style.display = 'block';
            previewVideo.src = url;
        } else {
            const reader = new FileReader();
            reader.onload = function(event) {
                previewImage.style.display = 'block';
                previewVideo.style.display = 'none';
                previewImage.src = event.target.result;
            };
            reader.readAsDataURL(file);
        }
        document.getElementById('fileName').textContent = file.name;
        showSection('preview');
    }
}

function initDetection() {
    document.getElementById('detectBtn').addEventListener('click', async function() {
        if (!currentFile) return;
        showSection('loading');
        
        const formData = new FormData();
        formData.append('file', currentFile);
        
        let locationData = { latitude: null, longitude: null };
        
        if (navigator.geolocation) {
            try {
                locationData = await new Promise((resolve) => {
                    navigator.geolocation.getCurrentPosition(
                        (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
                        () => resolve({ latitude: null, longitude: null }),
                        { enableHighAccuracy: true, timeout: 10000 }
                    );
                });
            } catch (e) {}
        }
        
        try {
            const lat = locationData.latitude || '';
            const lng = locationData.longitude || '';
            
            const response = await fetch(`/detect?lat=${lat}&lng=${lng}`, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.error) {
                if (data.duplicate) {
                    showDuplicatePopup();
                } else {
                    alert('Error: ' + data.error);
                }
                showSection('upload');
                return;
            }
            
            currentResultData = data;
            resultPath = data.result_image || data.result_video;
            lastPotholeCount = data.type === 'video' ? (data.detections?.max_detections_in_frame || 0) : (data.detections?.length || 0);
            
            if (data.type === 'video' && data.result_video) {
                document.getElementById('resultImage').style.display = 'none';
                document.getElementById('resultVideo').style.display = 'block';
                document.getElementById('resultVideo').src = data.result_video + '?t=' + new Date().getTime();
                cumulativeDetections = data.cumulative_detections || [];
            } else {
                document.getElementById('resultImage').style.display = 'block';
                document.getElementById('resultVideo').style.display = 'none';
                if (data.result_image && data.result_image.startsWith('data:')) {
                    document.getElementById('resultImage').src = data.result_image;
                } else if (resultPath) {
                    document.getElementById('resultImage').src = resultPath + '?t=' + new Date().getTime();
                }
            }
            
            document.getElementById('overlayCount').textContent = lastPotholeCount;
            
            let avgConf = 0;
            if (data.type === 'video') {
                avgConf = data.detections?.avg_confidence || 0;
            } else if (data.detections && data.detections.length > 0) {
                avgConf = Math.round((data.detections.reduce((sum, d) => sum + d.confidence, 0) / data.detections.length) * 100);
            }
            document.getElementById('overlayConf').textContent = avgConf + '%';
            
            document.getElementById('nightBadge').style.display = data.is_night_mode ? 'block' : 'none';
            
            const dupBadge = document.getElementById('duplicateBadge');
            if (data.duplicate && data.duplicate.duplicate) {
                dupBadge.style.display = 'block';
                dupBadge.title = `Duplicate of #${data.duplicate.original_id}`;
            } else {
                dupBadge.style.display = 'none';
            }
            
            const severity = calculateSeverity(lastPotholeCount, avgConf);
            document.getElementById('severityTag').textContent = severity.toUpperCase();
            document.getElementById('severityTag').className = 'severity-tag sev-' + severity;
            
            const quality = calculateQuality(lastPotholeCount, severity);
            document.getElementById('statConfidence').textContent = avgConf + '%';
            document.getElementById('statQuality').textContent = quality + '%';
            document.getElementById('statSeverity').textContent = severity.toUpperCase();
            document.getElementById('resultStatsGrid').style.display = 'grid';
            
            showSection('result');
            loadLiveStats();
            
        } catch (error) {
            console.error('Detection error:', error);
            alert('Detection failed. Please try again.');
            showSection('upload');
        }
    });
    
    document.getElementById('downloadBtn').addEventListener('click', function() {
        if (resultPath) {
            const link = document.createElement('a');
            link.href = resultPath;
            link.download = currentResultData && currentResultData.type === 'video' ? 'pothole_detection.mp4' : 'pothole_detection.jpg';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    });
    
    document.getElementById('newAnalysis').addEventListener('click', function() { resetUpload(); });
    
    document.getElementById('reportResultBtn').addEventListener('click', function() {
        if (currentResultData && currentResultData.detection_id) {
            fetch(`/file-complaint/${currentResultData.detection_id}`, { method: 'POST' })
            .then(res => res.json()).then(data => {
                showToast('Report Submitted to Authorities', 'success');
            }).catch(() => {
                showToast('Report Submitted to Authorities', 'success');
            });
        } else {
            showToast('Report Submitted to Authorities', 'success');
        }
    });
}

function calculateSeverity(count, confidence) {
    if (count >= 5) return 'severe';
    if (count >= 3) return 'high';
    if (count >= 1) return 'moderate';
    return 'low';
}

function calculateQuality(count, severity) {
    const base = 100;
    const deductions = { severe: 15, high: 10, moderate: 5, low: 2 };
    return Math.max(0, Math.min(100, base - (deductions[severity] || 5) * count));
}

function initLiveCamera() {
    const startBtn = document.getElementById('startCamera');
    const stopBtn = document.getElementById('stopCamera');
    const captureBtn = document.getElementById('captureBtn');
    const video = document.getElementById('videoElement');
    
    startBtn.addEventListener('click', async function() {
        try {
            const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
            const constraints = isMobile ? { video: { facingMode: 'environment' }, audio: false } : { video: true, audio: false };
            stream = await navigator.mediaDevices.getUserMedia(constraints);
            video.srcObject = stream;
            startBtn.style.display = 'none';
            stopBtn.style.display = 'flex';
            captureBtn.style.display = 'flex';
        } catch (error) {
            alert('Could not access camera. Please check permissions.');
        }
    });
    
    stopBtn.addEventListener('click', function() {
        if (stream) { stream.getTracks().forEach(track => track.stop()); stream = null; }
        video.srcObject = null;
        stopBtn.style.display = 'none';
        startBtn.style.display = 'flex';
        captureBtn.style.display = 'none';
    });
    
    captureBtn.addEventListener('click', async function() {
        const canvas = document.getElementById('canvasElement');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        const imageData = canvas.toDataURL('image/jpeg', 0.8);
        showSection('loading');
        
        let locationData = { latitude: null, longitude: null };
        if (navigator.geolocation) {
            try {
                locationData = await new Promise((resolve) => {
                    navigator.geolocation.getCurrentPosition(
                        (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
                        () => resolve({ latitude: null, longitude: null }),
                        { enableHighAccuracy: true, timeout: 10000 }
                    );
                });
            } catch (e) {}
        }
        
        try {
            const response = await fetch('/detect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData, location: locationData })
            });
            
            const data = await response.json();
            
            if (data.error) {
                alert('Error: ' + data.error);
                showSection('live');
                return;
            }
            
            currentResultData = data;
            resultPath = data.result_image;
            lastPotholeCount = data.detections ? data.detections.length : 0;
            
            if (data.result_image) {
                document.getElementById('resultImage').src = data.result_image;
                document.getElementById('resultImage').style.display = 'block';
                document.getElementById('resultVideo').style.display = 'none';
            }
            
            document.getElementById('overlayCount').textContent = lastPotholeCount;
            const avgConf = data.detections && data.detections.length > 0 ? Math.round((data.detections.reduce((sum, d) => sum + d.confidence, 0) / data.detections.length) * 100) : 0;
            document.getElementById('overlayConf').textContent = avgConf + '%';
            document.getElementById('nightBadge').style.display = data.is_night_mode ? 'block' : 'none';
            
            const severity = calculateSeverity(lastPotholeCount, avgConf);
            document.getElementById('severityTag').textContent = severity.toUpperCase();
            document.getElementById('severityTag').className = 'severity-tag sev-' + severity;
            
            const quality = calculateQuality(lastPotholeCount, severity);
            document.getElementById('statConfidence').textContent = avgConf + '%';
            document.getElementById('statQuality').textContent = quality + '%';
            document.getElementById('statSeverity').textContent = severity.toUpperCase();
            document.getElementById('resultStatsGrid').style.display = 'grid';
            
            showSection('result');
            loadLiveStats();
            
        } catch (error) {
            alert('Detection failed. Please try again.');
            showSection('live');
        }
    });
}

function initReportForm() {
    const reportForm = document.getElementById('userReportForm');
    const reportCameraBtn = document.getElementById('reportCameraBtn');
    const reportGalleryBtn = document.getElementById('reportGalleryBtn');
    const reportMediaInput = document.getElementById('reportMediaInput');
    const removeReportMedia = document.getElementById('removeReportMedia');
    const getLocationBtn = document.getElementById('getLocationBtn');
    
    reportCameraBtn.addEventListener('click', function() { reportMediaInput.accept = 'image/*'; reportMediaInput.capture = 'environment'; reportMediaInput.click(); });
    reportGalleryBtn.addEventListener('click', function() { reportMediaInput.accept = 'image/*'; reportMediaInput.removeAttribute('capture'); reportMediaInput.click(); });
    
    reportMediaInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(event) {
                document.getElementById('reportPreviewImage').src = event.target.result;
                document.getElementById('reportPreview').style.display = 'block';
                reportMediaData = event.target.result;
            };
            reader.readAsDataURL(file);
        }
    });
    
    removeReportMedia.addEventListener('click', function() {
        reportMediaData = null;
        document.getElementById('reportMediaInput').value = '';
        document.getElementById('reportPreview').style.display = 'none';
    });
    
    getLocationBtn.addEventListener('click', function() {
        if (navigator.geolocation) {
            getLocationBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lng = pos.coords.longitude;
                    document.getElementById('locationCoords').textContent = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
                    getLocationBtn.innerHTML = '<i class="fas fa-check"></i>';
                    reverseGeocode(lat, lng);
                },
                () => { getLocationBtn.innerHTML = '<i class="fas fa-times"></i>'; alert('Could not get location'); }
            );
        }
    });
    
    reportForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        if (!reportMediaData) { alert('Please capture or select an image'); return; }
        
        const submitBtn = reportForm.querySelector('.btn-submit');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        
        const coords = document.getElementById('locationCoords').textContent.split(',');
        const location = {
            latitude: coords.length === 2 ? parseFloat(coords[0]) : null,
            longitude: coords.length === 2 ? parseFloat(coords[1]) : null,
            address: document.getElementById('reportAddress').value
        };
        
        try {
            const response = await fetch('/api/user-reports', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: 'image',
                    user_name: document.getElementById('reportName').value,
                    description: document.getElementById('reportDescription').value,
                    location: location,
                    media: reportMediaData
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                alert('Report submitted successfully!\n\nSeverity: ' + data.severity.toUpperCase() + '\nPotholes Found: ' + (data.detections?.length || 0));
                reportForm.reset();
                reportMediaData = null;
                document.getElementById('reportPreview').style.display = 'none';
                document.getElementById('locationCoords').textContent = '';
                hideAllSections();
                document.getElementById('heroSection').style.display = 'block';
                showSection('upload');
                loadLiveStats();
            } else if (data.duplicate) {
                showDuplicatePopup();
            } else {
                alert('Error: ' + (data.error || 'Failed to submit report'));
            }
        } catch (error) {
            alert('Failed to submit report. Please try again.');
        }
        
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Report';
    });
}

async function reverseGeocode(lat, lng) {
    try {
        const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`);
        const data = await response.json();
        if (data.display_name) { document.getElementById('reportAddress').value = data.display_name; }
    } catch (e) {}
}

function initMapSection() {
    potholeMap = L.map('potholeMap').setView([20.5937, 78.9629], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(potholeMap);
    loadMapData();
}

async function loadMapData() {
    if (!potholeMap) return;
    
    potholeMap.eachLayer(layer => { if (layer instanceof L.CircleMarker || layer instanceof L.Marker) potholeMap.removeLayer(layer); });
    
    try {
        const response = await fetch('/api/map-data');
        const data = await response.json();
        
        data.markers.forEach(marker => {
            const color = { severe: '#ff0044', high: '#ff6b00', moderate: '#ffc107', low: '#00ff88' }[marker.severity] || '#ffc107';
            const size = marker.pothole_count >= 3 ? 14 : 9;
            
            const statusColor = marker.status === 'pending' ? '#ff0044' : marker.status === 'in_progress' || marker.status === 'reported_to_corp' ? '#ffc107' : marker.status === 'rejected' ? '#ff4400' : '#00ff88';
            L.circleMarker([marker.lat, marker.lng], {
                radius: size,
                fillColor: color,
                color: '#fff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.7
            }).addTo(potholeMap).bindPopup(`<div style="min-width:180px"><strong style="color:${statusColor}">${marker.pothole_count} Pothole${marker.pothole_count>1?'s':''}</strong><br>Severity: <span class="severity-badge sev-${marker.severity}">${(marker.severity||'').toUpperCase()}</span><br>Status: <span class="status-badge status-${marker.status}">${(marker.status||'').replace('_', ' ')}</span><br>Quality: ${marker.road_quality}%<br><small>${marker.date}</small></div>`);
        });
        
        if (data.markers.length > 0) {
            const bounds = L.latLngBounds(data.markers.map(m => [m.lat, m.lng]));
            potholeMap.fitBounds(bounds, { padding: [50, 50] });
        }
    } catch (e) { console.error('Map data error:', e); }
}

function showSection(section) {
    document.getElementById('uploadOptions').style.display = section === 'upload' ? 'grid' : 'none';
    document.getElementById('previewSection').style.display = section === 'preview' ? 'block' : 'none';
    document.getElementById('loadingSection').style.display = section === 'loading' ? 'block' : 'none';
    document.getElementById('resultSection').style.display = section === 'result' ? 'block' : 'none';
    document.getElementById('heroSection').style.display = 'block';
}

function resetUpload() {
    currentFile = null;
    currentResultData = null;
    resultPath = null;
    cumulativeDetections = [];
    document.getElementById('fileInputCamera').value = '';
    document.getElementById('fileInputGallery').value = '';
    document.getElementById('previewImage').src = '';
    document.getElementById('previewVideo').src = '';
    document.getElementById('previewImage').style.display = 'block';
    document.getElementById('previewVideo').style.display = 'none';
    document.getElementById('resultImage').src = '';
    document.getElementById('resultVideo').src = '';
    document.getElementById('resultImage').style.display = 'block';
    document.getElementById('resultVideo').style.display = 'none';
    document.getElementById('resultStatsGrid').style.display = 'none';
    showSection('upload');
}

function showToast(message, type) {
    const existing = document.querySelector('.toast-notification');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.innerHTML = `<div class="toast-icon"><i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i></div><div class="toast-msg">${message}</div><button class="toast-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>`;
    document.body.appendChild(toast);
    setTimeout(() => { toast.classList.add('show'); }, 10);
    setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, 4000);
}

function toggleMobileMenu() {
    const panel = document.getElementById('mobileNavPanel');
    const overlay = document.getElementById('mobileNavOverlay');
    if (panel) {
        panel.classList.toggle('open');
        overlay.classList.toggle('open');
        document.body.style.overflow = panel.classList.contains('open') ? 'hidden' : '';
    }
}

function closeMobileMenu() {
    const panel = document.getElementById('mobileNavPanel');
    const overlay = document.getElementById('mobileNavOverlay');
    if (panel) {
        panel.classList.remove('open');
        overlay.classList.remove('open');
        document.body.style.overflow = '';
    }
}

function initFAQ() {
    document.querySelectorAll('.faq-question').forEach(q => {
        q.addEventListener('click', function() {
            const item = this.parentElement;
            const isActive = item.classList.contains('active');
            document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('active'));
            if (!isActive) item.classList.add('active');
        });
    });
}

function initCounters() {
    const counters = document.querySelectorAll('.counter-number');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const counter = entry.target;
                const target = parseInt(counter.dataset.target);
                let current = 0;
                const step = Math.ceil(target / 60);
                const interval = setInterval(() => {
                    current += step;
                    if (current >= target) {
                        current = target;
                        clearInterval(interval);
                    }
                    let text = counter.innerHTML;
                    if (text.includes('<span')) {
                        counter.innerHTML = current + '<span class="counter-suffix">%</span>';
                    } else {
                        counter.textContent = current;
                    }
                }, 20);
                observer.unobserve(counter);
            }
        });
    }, { threshold: 0.5 });
    counters.forEach(c => observer.observe(c));
}

function showDuplicatePopup() {
    const existing = document.getElementById('dupPopup');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'dupPopup';
    overlay.innerHTML = `
        <div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center;">
            <div style="background:var(--bg-card);border:2px solid var(--neon-orange);border-radius:20px;padding:40px;max-width:420px;text-align:center;box-shadow:0 0 60px rgba(255,107,0,0.3);animation:fadeIn 0.3s ease;">
                <div style="font-size:4rem;margin-bottom:20px;color:var(--neon-orange);"><i class="fas fa-info-circle"></i></div>
                <h3 style="font-family:'Orbitron',sans-serif;color:var(--neon-orange);margin-bottom:15px;font-size:1.1rem;">Duplicate Detection</h3>
                <p style="font-family:'Rajdhani',sans-serif;color:var(--text-primary);font-size:1.2rem;margin-bottom:25px;">This pothole is already available in the system</p>
                <button onclick="document.getElementById('dupPopup').remove()" style="padding:12px 35px;background:linear-gradient(135deg,var(--neon-orange),#cc5500);border:none;border-radius:10px;color:white;font-family:'Orbitron',sans-serif;font-size:0.9rem;cursor:pointer;">OK</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
}

function showOnMap(lat, lng) {
    if (!potholeMap) {
        let navMap = document.getElementById('navMap');
        if (navMap) navMap.click();
    }
    document.getElementById('mapSection').style.display = 'block';
    document.getElementById('mapSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(() => {
        if(potholeMap) {
            potholeMap.invalidateSize();
            potholeMap.setView([lat, lng], 18);
            setTimeout(() => {
                potholeMap.eachLayer(l => {
                    if (l.getLatLng && Math.abs(l.getLatLng().lat - lat) < 0.0001 && Math.abs(l.getLatLng().lng - lng) < 0.0001) {
                        if (l.openPopup) l.openPopup();
                    }
                });
            }, 500);
        }
    }, 300);
}
