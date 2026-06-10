# TECH سلام - AI-Powered Smart Emergency Detection System 
Tech سلام is an integrated security and safety solution that uses Computer Vision and IoT sensors to detect life-threatening emergencies in real-time. By combining a YOLO-based AI model with hardware sensors, the system identifies fire, smoke, weapons, and falls, providing instant alerts through a centralized web dashboard.

# 1. Team Members
- **Lujain Tayyarah** - Team Leader & System Engineer
   - Hardware Integration
   - Frontend development
   - Full Stack Backend Development
   - Hardware-To-Web Connection
   - AI Model Training
   - System Calibration

- **Njood AlKhamis** - System Engineer
   - Hardware Integration
   - Hardware-To-Web Connection
   - System Calibration
   - AI Model Training
   - Dataset Labeling
   - System testing
   - Dataset Collection and Preparation

 
- **Noura AlDrees** - System Engineer
  - Dataset Collection and Preparation
  - AI Model Training
  - Arduino Uno Integration

- **Rahaf Alquwaider** - System Engineer
  - Backend Development
  - Arduino Uno Integration
  - System Testing
    
# 2. Project Overview
Use Case: Conventional security systems require manual monitoring, which leads to slow response times during fires or violent incidents.
Tech سلام addresses this by offering:
- Automated Threat Detection: AI that never sleeps, identifying weapons and fire instantly.
- IoT Synergy: Using MQ-2 sensors to detect smoke/gas before a fire is even visible.
- Centralized Monitoring: A web-based dashboard for security personnel to view live feeds and historical logs.
# 3. Application Features
A. AI Computer Vision (YOLO)
- Real-time detection of: Fire, Smoke, Weapons (Guns/Knives), and Human Falls.
- Optimized "Nano" model for high-speed inference on edge devices (Raspberry Pi).
- Live-stream overlay with detection bounding boxes and confidence scores.

B. Smart Emergency Logging
- Database Integration: Every detected emergency is automatically logged into an SQLite database.
- Anti-Spam Logic: Implemented a 10-second cooldown timer for logs to prevent database flooding during continuous detection.
- User-Specific Logs: Emergencies are linked to the specific user's account for personalized security history.

C. Hardware & Sensor Alerts
- MQ-2 Gas/Smoke Sensor: Detects smoke levels at a 40-threshold limit.
- Physical Alarm: Arduino-controlled 5V buzzer and LCD screen for local on-site alerts.
- Headless Pi Management: Remote system control via SSH.

D. User Dashboard (Flask)
- Secure Authentication: Login/Register system with hashed passwords.
- Livestream Interface: Low-latency video feed using OpenCV.
- Emergency Logs: A modern, filtered table showing severity, event type, and timestamps.
  
# 4. Technology Stack
- AI/ML: YOLOv8(Ultralytics), Google Colab (Training)
- Backend: Python, Flask, Flask-SQLAlchemy
- Frontend: HTML5, CSS3 (Modern UI), Jinja2 Templates
- Hardware: Raspberry Pi 4/5, Arduino Uno, MQ-2 Sensor, Pi Camera
- Database: SQLite
- Computer Vision: OpenCV (cv2)

# 5. Setup Instructions
- **Step 1: Clone and Install Dependencies**
```
git clone https://github.com/ra-f21/smart-emergency-detection-system
cd tech-salam
pip install -r requirements.txt
  ```
- **Step 2: Hardware Connection**
- Connect the MQ-2 Sensor and Buzzer to the Arduino Uno.
- Connect the Arduino to the Raspberry Pi.
- Ensure the Camera is enabled in raspi-config.

- **Step 3: Add the AI Model**
- Place your trained best.pt file in the root directory of the project.

- **Step 4: Run the Application**
```
py app.py
```

# The application will be accessible at:
http://localhost:5000 or http://[YOUR_PI_IP]:5000

# 6. System Architecture

The system consists of the following components:

1. USB Camera
   → Captures live video frames

2. YOLOv8 Detection Module
   → Detects Fire, Smoke, Fall, Sit, Gun, and Knife 

3. MQ-2 Sensor + Arduino Uno
   → Detects gas/smoke levels

4. Raspberry Pi
   → Runs Flask backend and AI model

5. SQLite Database
   → Stores users and emergency logs

6. Web Dashboard
   → Displays livestream and emergency logs

# 7. AI Model

Model: YOLOv8n

Classes:
- Fire
- Smoke
- Fall
- Sit
- Gun
- Knife

Training Images:
76,216

Training Platform:
Google Colab (H100 GPU)

Epochs:
50
   
