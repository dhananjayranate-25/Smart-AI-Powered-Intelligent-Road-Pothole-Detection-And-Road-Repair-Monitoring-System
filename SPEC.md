# Pothole Detection System - Specification

## Project Overview
- **Project Name**: PotholeAI
- **Type**: Web Application
- **Core Functionality**: AI-powered system that detects potholes in road images/videos with advanced features including citizen reporting, hotspot detection, and authority notification
- **Target Users**: Road maintenance teams, city planners, drivers, citizens

## Tech Stack
- **Backend**: Python with Flask
- **Frontend**: HTML, CSS, JavaScript
- **ML Model**: YOLOv8 (pretrained on road damage dataset, fine-tuned for potholes)
- **Image Processing**: OpenCV, Pillow
- **Maps**: Leaflet.js with OpenStreetMap

## New Features Implemented

### 1. User Report Option (Video + Photo)
- **Citizen Report Form**: Users can submit pothole reports with their name, location, and media
- **Photo/Video Capture**: Camera and gallery options for capturing evidence
- **Location Auto-detect**: GPS location with reverse geocoding for address
- **Severity Selection**: Users can indicate pothole severity
- **Description Field**: Additional details about the pothole condition
- **Automatic Detection**: Submitted media is automatically analyzed by AI

### 2. Duplicate Detection
- **Location-based Detection**: Identifies if a new report is within 100m of existing reports
- **Time Window**: Checks last 7 days for duplicates
- **Visual Indicators**: Badges showing duplicate status on detections
- **Link to Original**: Shows reference to original detection
- **Duplicate Management Panel**: Admin view of all duplicate reports

### 3. Night Detection Improvement
- **Automatic Brightness Analysis**: Detects low-light conditions (avg brightness < 100)
- **CLAHE Enhancement**: Contrast Limited Adaptive Histogram Equalization
- **Gamma Correction**: 1.5 gamma correction for dark image adjustment
- **Image Sharpening**: Kernel-based sharpening for edge enhancement
- **Lower Confidence Threshold**: 0.15 for night mode vs 0.25 for day
- **Visual Alerts**: Yellow warning labels and cross markers for night detections
- **Night Badge**: Displayed on results showing night mode was used

### 4. Road Quality Score
- **Automatic Calculation**: Based on pothole count and severity
- **Score Range**: 0-100 (100 = perfect road)
- **Severity-based Deduction**:
  - Severe: -15 points per pothole
  - High: -10 points per pothole
  - Moderate: -5 points per pothole
  - Low: -2 points per pothole
- **Quality Map Layer**: Color-coded zones showing road quality
- **Zone Aggregation**: Groups nearby detections for area analysis

### 5. Heatmap (Hotspot Detection)
- **Hotspot Identification**: Zones with 2+ potholes within proximity
- **Clustering Algorithm**: Groups detections within 0.5km radius
- **Interactive Map**: Leaflet.js with multiple layers
- **Visual Heat Zones**: Circle markers sized by pothole count
- **Severity-based Colors**: Red for severe, orange for high, yellow for moderate
- **Last Updated Tracking**: Shows when hotspot was last refreshed
- **Admin Hotspot Panel**: Detailed view with statistics and map
- **Multiple Map Views**: Markers, Heatmap, Road Quality layers

### 6. Automatic Report to Authority
- **Authority Configuration**: Name and email for municipal/road authority
- **Batch Reporting**: Submit multiple detections at once
- **Priority Levels**: Normal, High (severe only), Critical
- **Hotspot Inclusion**: Includes hotspot zone data in reports
- **Report ID Generation**: Unique ID format: AR + timestamp + random
- **Report Tracking**: History of all submitted reports
- **Complaint ID Assignment**: Links reports to individual detections
- **Status Updates**: Track report submission status

## Database Models

### Detection (Enhanced)
- `is_night_detection`: Boolean flag for night mode detections
- `duplicate_of_id`: Reference to original detection if duplicate
- `reported_by_user`: Citizen reporter name
- `user_description`: User-provided description

### HotspotZone (New)
- `center_lat`, `center_lng`: Zone center coordinates
- `radius_km`: Detection radius (default 0.5km)
- `pothole_count`: Number of potholes in zone
- `avg_severity`: Zone's average severity
- `report_count`: Number of reports in zone

### AuthorityReport (New)
- `report_id`: Unique report identifier
- `authority_name`, `authority_email`: Recipient info
- `detection_ids`: JSON list of included detections
- `total_potholes`: Sum of all potholes in report
- `hotspot_zones`: JSON of included hotspot data
- `status`: Report submission status

## API Endpoints

### Existing
- `GET /api/stats`: Statistics and severity counts
- `GET /api/map-data`: All detections with location data
- `POST /api/gps-track`: Record GPS route data

### New Endpoints
- `GET /api/hotspots`: List all hotspot zones
- `GET /api/road-quality-map`: Road quality zone data
- `GET /api/duplicates`: List duplicate detections (admin)
- `POST /api/user-reports`: Submit citizen report
- `POST /report-authority`: Submit report to authority (admin)
- `GET /api/authority-reports`: List submitted reports (admin)

## UI/UX Specification

### Color Palette
- Primary: #00f0ff (Neon Cyan)
- Secondary: #ff00ff (Neon Pink)
- Purple: #bf00ff (Neon Purple) - for reports
- Success: #00ff88 (Neon Green)
- Warning: #ff6b00 (Neon Orange)
- Danger: #ff0044 (Neon Red)
- Background: #0a0a12 (Dark)
- Card: #12121a (Card Dark)

### Severity Colors
- Low: #00ff88 (Green)
- Moderate: #ffc107 (Yellow)
- High: #ff6b00 (Orange)
- Severe: #ff0044 (Red)

### Typography
- Headings: 'Orbitron', sans-serif
- Body: 'Rajdhani', sans-serif

## Acceptance Criteria
1. User can submit a report with photo/video, name, location, and description
2. Duplicate detections within 100m/7 days are flagged
3. Night mode activates automatically for low-light images
4. Road quality score updates based on detections
5. Hotspots appear on map for zones with 2+ potholes
6. Admin can submit batch reports to authorities
7. All features work on mobile and desktop
8. Application runs without errors
