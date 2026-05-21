from ultralytics import YOLO
import os

model = YOLO('yolov8n.pt')

results = model.train(
    data='archive (1)/data.yaml',
    epochs=10,
    imgsz=416,
    batch=8,
    project='runs/train',
    name='pothole',
    exist_ok=True
)

print("Training complete!")
print(f"Best model saved at: runs/train/pothole/weights/best.pt")
