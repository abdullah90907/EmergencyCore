# EmergencyCore: AI-Powered Disaster Response Platform

## Overview
EmergencyCore is an advanced AI-driven platform designed to enhance disaster response and management through intelligent analysis of citizen reports, damage detection, and emergency forecasting.

## Features
- **Text Analysis**: Classify and prioritize emergency reports
- **Image Analysis**: Detect and assess damage from disaster scenes
- **Weather Prediction**: Coming soon!

## Setup & Installation

### Prerequisites
- Python 3.9+
- pip
- Virtual Environment (recommended)

### Installation Steps
1. Clone the repository
```bash
git clone https://github.com/yourusername/emergency-core.git
cd emergency-core
```

2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

3. Install Dependencies
```bash
pip install -r requirements.txt
```

4. Run the Application
```bash
streamlit run src/main.py
```

## Technologies
- Streamlit
- Hugging Face Transformers
- YOLOv5
- PyTorch

## License
MIT License
