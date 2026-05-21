import os
import uuid
import cv2
import numpy as np
from ultralytics import YOLO
from PIL import Image

MODEL_PATH = 'best.pt'

def calculate_iou(box1, box2):
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)
    
    if inter_x_max <= inter_x_min or inter_y_max <= inter_y_min:
        return 0.0
    
    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    union_area = box1_area + box2_area - inter_area
    
    return inter_area / union_area if union_area > 0 else 0.0

def apply_nms(boxes, confidences, iou_threshold=0.4):
    if len(boxes) == 0:
        return [], []
    
    indices = sorted(range(len(confidences)), key=lambda i: confidences[i], reverse=True)
    
    keep_boxes = []
    keep_confidences = []
    
    while indices:
        current = indices.pop(0)
        keep_boxes.append(boxes[current])
        keep_confidences.append(confidences[current])
        
        indices = [
            i for i in indices
            if calculate_iou(boxes[current], boxes[i]) < iou_threshold
        ]
    
    return keep_boxes, keep_confidences

class PotholeDetector:
    def __init__(self):
        self.model = None
        for path in [MODEL_PATH, 'yolov8n.pt']:
            try:
                self.model = YOLO(path)
                print(f"Loaded model: {path}")
                break
            except Exception as e:
                print(f"Failed to load {path}: {e}")
        if self.model is None:
            raise RuntimeError("No YOLO model could be loaded")
        self.night_threshold = 100
        
    def enhance_for_night(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        avg_brightness = np.mean(gray)
        
        if avg_brightness < self.night_threshold:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)
            
            gamma = 1.5
            l_gamma = np.array(255 * (l_enhanced / 255) ** (1/gamma), dtype=np.uint8)
            
            enhanced_lab = cv2.merge([l_gamma, a, b])
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]]) / 9
            sharpened = cv2.filter2D(enhanced, -1, kernel)
            enhanced = cv2.addWeighted(enhanced, 0.7, sharpened, 0.3, 0)
            
            return True, enhanced
        
        return False, img
    
    def preprocess(self, img):
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        return enhanced
    
    def filter_by_size(self, boxes, confidences, img_w, img_h):
        img_area = img_w * img_h
        min_area = img_area * 0.0005
        max_area = img_area * 0.4
        filtered_b, filtered_c = [], []
        for box, conf in zip(boxes, confidences):
            x1, y1, x2, y2 = box
            w, h = x2 - x1, y2 - y1
            area = w * h
            aspect = max(w, h) / (min(w, h) + 0.001)
            if min_area <= area <= max_area and aspect < 6:
                filtered_b.append(box)
                filtered_c.append(conf)
        return filtered_b, filtered_c
    
    def run_detection(self, img, conf_threshold=0.10, imgsz=640):
        h, w = img.shape[:2]
        results = self.model(img, conf=conf_threshold, save=False, imgsz=imgsz, verbose=False)
        boxes, confs = [], []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                boxes.append([int(x1), int(y1), int(x2), int(y2)])
                confs.append(conf)
        boxes, confs = self.filter_by_size(boxes, confs, w, h)
        return boxes, confs
    
    def detect_image(self, image_path, night_mode=False):
        img = cv2.imread(image_path)
        
        is_night, processed = self.enhance_for_night(img)
        is_night = is_night or night_mode
        if not is_night:
            processed = self.preprocess(img)
        
        all_boxes, all_confs = self.run_detection(processed)
        
        
        
        boxes, confidences = apply_nms(all_boxes, all_confs, iou_threshold=0.5)
        
        final_boxes, final_confs = [], []
        for box, conf in zip(boxes, confidences):
            if conf >= 0.15:
                final_boxes.append(box)
                final_confs.append(conf)
        
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        detections = []
        bbox_colors = [
            (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255),
            (255, 0, 255), (0, 255, 255), (128, 0, 255), (255, 128, 0)
        ]
        
        for idx, (box, conf) in enumerate(zip(final_boxes, final_confs)):
            x1, y1, x2, y2 = box
            
            color = bbox_colors[idx % len(bbox_colors)]
            if night_mode or is_night:
                color = (0, 255, 255)
            
            cv2.rectangle(img_rgb, (x1, y1), (x2, y2), color, 3)
            
            if night_mode or is_night:
                cv2.line(img_rgb, (x1, y1), (x2, y2), color, 2)
                cv2.line(img_rgb, (x2, y1), (x1, y2), color, 2)
            
            label = f'Pothole {conf:.2f}'
            if night_mode or is_night:
                label = f'[!] {label}'
            
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(img_rgb, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), color, -1)
            cv2.putText(img_rgb, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            detections.append({
                'bbox': [x1, y1, x2, y2],
                'confidence': round(conf, 3)
            })
        
        result_filename = f"result_{uuid.uuid4().hex}.jpg"
        result_path = os.path.join('results', result_filename)
        img_pil = Image.fromarray(img_rgb)
        img_pil.save(result_path)
        
        return result_path, detections, is_night
    
    def detect_video(self, video_path):
        cap = cv2.VideoCapture(video_path)
        
        fourcc = cv2.VideoWriter_fourcc(*'H264')
        result_filename = f"result_{uuid.uuid4().hex}.mp4"
        result_path = os.path.join('results', result_filename)
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        out = cv2.VideoWriter(result_path, fourcc, fps, (width, height))
        
        total_detections = 0
        total_confidence = 0.0
        max_detections_in_frame = 0
        frames_with_detections = 0
        cumulative_detections_list = []
        
        frame_skip = 5
        last_annotated_frame = None
        frame_index = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            annotated_frame = frame.copy()
            
            if frame_index % frame_skip == 0:
                is_night, enhanced_frame = self.enhance_for_night(frame)
                conf_threshold = 0.15 if is_night else 0.20
                
                results = self.model(enhanced_frame, conf=conf_threshold, save=False)
                
                frame_boxes = []
                frame_confs = []
                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0])
                        frame_boxes.append([int(x1), int(y1), int(x2), int(y2)])
                        frame_confs.append(conf)
                
                filtered_boxes, filtered_confs = apply_nms(frame_boxes, frame_confs, iou_threshold=0.4)
                
                frame_detections = 0
                for idx, (box, conf) in enumerate(zip(filtered_boxes, filtered_confs)):
                    x1, y1, x2, y2 = box
                    
                    color = (0, 255, 255) if is_night else (255, 0, 0)
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)
                    label = f'Pothole {conf:.2f}'
                    if is_night:
                        label = f'[!] {label}'
                    cv2.putText(annotated_frame, label, (x1, y1 - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    
                    total_detections += 1
                    total_confidence += conf
                    frame_detections += 1
                
                if frame_detections > max_detections_in_frame:
                    max_detections_in_frame = frame_detections
                if frame_detections > 0:
                    frames_with_detections += 1
                
                last_annotated_frame = annotated_frame
            
            out.write(last_annotated_frame)
            cumulative_detections_list.append(total_detections)
            frame_index += 1
        
        cap.release()
        out.release()
        
        avg_confidence = round((total_confidence / total_detections * 100), 1) if total_detections > 0 else 0
        
        return result_path, {
            'total_frames': frame_index, 
            'total_detections': total_detections,
            'max_detections_in_frame': max_detections_in_frame,
            'frames_with_detections': frames_with_detections,
            'avg_confidence': avg_confidence,
            'fps': fps,
            'cumulative_detections': cumulative_detections_list
        }
