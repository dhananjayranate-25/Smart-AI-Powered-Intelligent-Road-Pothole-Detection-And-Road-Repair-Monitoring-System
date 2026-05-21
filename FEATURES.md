# PotholeAI - Features Implementation Guide

## Overview
This document explains all features implemented in the Pothole Detection System.

---

## 1. User Report System (Citizen Reporting)

### Purpose
Allows citizens to report potholes with photos, videos, and location data.

### How to Use
1. Click **"Report"** button in navigation bar
2. Fill in your name
3. Click GPS button to auto-detect location (or enter manually)
4. Click **Camera** or **Gallery** to attach photo/video
5. Add description and select severity
6. Click **Submit Report**

### What Happens
- Media is automatically analyzed by AI
- Detection count and severity are calculated
- Data is saved to database with user info
- Hotspots are updated automatically

### API Endpoint
```
POST /api/user-reports
```

---

## 2. Duplicate Detection

### Purpose
Prevents counting same pothole multiple times. If someone reports same location within 7 days, it's marked as duplicate.

### How it Works
- Location radius: 100 meters (0.1 km)
- Time window: 7 days
- Shows badge "Duplicate Detected" on results
- Links to original detection ID

### Visual Indicators
- 🌙 Night badge on night detections
- 📋 Duplicate badge on repeated reports
- Orange border on duplicate entries

### API Endpoint
```
GET /api/duplicates (Admin only)
```

---

## 3. Night Detection Improvement

### Purpose
Enhances detection accuracy for low-light images (night time, shadows, tunnels).

### Enhancement Techniques
1. **Brightness Analysis**: Detects if avg brightness < 100
2. **CLAHE**: Contrast Limited Adaptive Histogram Equalization
3. **Gamma Correction**: 1.5 gamma for dark images
4. **Sharpening**: Kernel-based edge enhancement
5. **Lower Threshold**: conf=0.25 for night vs 0.35 for day

### Visual Changes in Night Mode
- Yellow bounding boxes (instead of red)
- Cross markers on boxes
- "Night Mode" badge displayed
- Warning labels "[!]"

### API Response
```json
{
  "is_night_mode": true,
  "detections": [...]
}
```

---

## 4. Road Quality Score

### Purpose
Calculates overall road condition score (0-100) based on potholes.

### Calculation Formula
```
Base Score = 100

Deductions:
- Severe:   -15 points per pothole
- High:     -10 points per pothole  
- Moderate:  -5 points per pothole
- Low:      -2 points per pothole
```

### Example
- 3 severe potholes: 100 - (3 × 15) = 55%
- 2 moderate potholes: 100 - (2 × 5) = 90%

### Severity Levels
| Potholes | Severity |
|----------|----------|
| 1+ | Moderate |
| 3+ | High |
| 5+ | Severe |

### API Endpoint
```
GET /api/road-quality-map
```

---

## 5. Heatmap / Hotspot Detection

### Purpose
Identifies areas with multiple potholes (hotspots) that need urgent attention.

### How it Works
1. Groups detections within proximity
2. Zones with 2+ potholes become hotspots
3. Severity based on worst pothole in zone
4. Interactive map visualization

### Map Layers
1. **Markers**: Individual detection points
2. **Heatmap**: Hotspot zones with circles
3. **Road Quality**: Color-coded quality zones

### Map Colors
- 🔴 Red: Severe (Quality < 40%)
- 🟠 Orange: High severity
- 🟡 Yellow: Moderate
- 🟢 Green: Low / Fixed

### API Endpoint
```
GET /api/hotspots
```

---

## 6. Automatic Report to Authority

### Purpose
Generate and submit reports to municipal/road authorities.

### How to Use (Admin)
1. Login to Admin Dashboard
2. Go to **Authority** tab
3. Enter authority name and email
4. Select priority level
5. Click **Submit Report**

### Priority Levels
- **Normal**: All pending detections
- **High**: Only severe/high severity
- **Critical**: All high/severe within limits

### What Gets Submitted
- List of detection IDs
- Total pothole count
- Hotspot zone data
- Severity breakdown
- Auto-generated Report ID

### Report ID Format
```
AR202604171230451234
AR + YYYYMMDDHHMMSS + Random4Digits
```

### API Endpoint
```
POST /report-authority (Admin only)
GET /api/authority-reports (Admin only)
```

---

## Database Models

### Detection Table
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| filename | String | Result image/video filename |
| file_type | String | 'image' or 'video' |
| latitude | Float | GPS latitude |
| longitude | Float | GPS longitude |
| address | String | Location address |
| pothole_count | Integer | Number detected |
| avg_confidence | Float | Average confidence % |
| severity | String | low/moderate/high/severe |
| road_quality_score | Integer | 0-100 score |
| status | String | pending/fixed/in_progress |
| complaint_filed | Boolean | Report submitted |
| complaint_id | String | Report ID |
| is_night_detection | Boolean | Night mode used |
| duplicate_of_id | Integer | Reference to original |
| reported_by_user | String | Citizen name |
| user_description | Text | User's description |

### HotspotZone Table
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| center_lat | Float | Zone center |
| center_lng | Float | Zone center |
| radius_km | Float | Detection radius |
| pothole_count | Integer | Count in zone |
| avg_severity | String | Zone severity |
| last_updated | DateTime | Last refresh |
| report_count | Integer | Number of reports |

### AuthorityReport Table
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| report_id | String | Unique report ID |
| authority_name | String | Recipient name |
| authority_email | String | Recipient email |
| detection_ids | Text | JSON list |
| total_potholes | Integer | Sum count |
| hotspot_zones | Text | JSON zone data |
| report_date | DateTime | Submission date |
| status | String | submitted/pending |
| authority_response | Text | Reply (future) |

---

## API Endpoints Summary

### Public Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Home page |
| GET | /login | Login page |
| POST | /detect | Analyze image/video |
| GET | /api/stats | Dashboard statistics |
| GET | /api/map-data | All detections |
| GET | /api/hotspots | Hotspot zones |
| GET | /api/road-quality-map | Quality zones |
| POST | /api/user-reports | Submit citizen report |
| POST | /api/gps-track | Record GPS route |

### Admin Endpoints (Requires Login)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /admin | Dashboard |
| POST | /update-status/<id> | Update status |
| POST | /delete-detection/<id> | Delete one |
| POST | /delete-all-detections | Delete all |
| GET | /export-csv | Export data |
| GET | /export-report | Generate report |
| GET | /api/duplicates | View duplicates |
| POST | /report-authority | Submit to authority |
| GET | /api/authority-reports | View reports |
| POST | /file-complaint/<id> | File complaint |

---

## File Structure

```
potholeai/
├── app.py              # Main Flask application
├── detection.py        # YOLO detection + NMS + Night enhancement
├── templates/
│   ├── index.html      # Home page with report form + map
│   ├── admin.html      # Admin dashboard with tabs
│   └── login.html      # Login page
├── static/
│   ├── script.js       # Frontend JavaScript
│   └── style.css       # Styles + new UI components
├── instance/
│   └── potholeai.db    # SQLite database
├── uploads/            # Original uploads
├── results/            # Detection results
├── best.pt             # Trained YOLO model
└── FEATURES.md         # This file
```

---

## Running the Application

```bash
# Start server
python app.py

# Access URLs
- Local:   http://localhost:5000
- Mobile:  http://<your-ip>:5000
- Admin:   http://localhost:5000/login
```

### Default Admin Credentials
- Username: `admin`
- Password: `admin123`

---

## Troubleshooting

### No detections found?
- Increase confidence threshold in `detection.py`
- Check image quality
- Ensure model `best.pt` exists

### Duplicate boxes on same pothole?
- NMS (Non-Maximum Suppression) is now enabled
- IOU threshold: 0.4
- Confidence threshold: 0.35 (day) / 0.25 (night)

### Night mode not working?
- Image brightness is calculated automatically
- Threshold: avg_gray < 100 triggers enhancement

### Map not loading?
- Check internet connection (needs OpenStreetMap)
- Ensure Leaflet.js CDN is accessible
