# 🎺 Marching Band Management System

This project is a desktop system designed to manage marching band students, equipment assignments, and eligibility tracking. It was designed with the structure and needs of **Florida A&M University’s Marching 100** in mind and built to explore database design, GUI development, and systems programming across multiple languages in one connected project.

This repository contains **two versions** of the system:

## 🖥 Python GUI Version (Primary)

Built with **Python and PySide6**, this is the full desktop application and the main version of the project.

**Features include**
- Student roster management  
- Instrument, uniform, and shako checkout tracking  
- Eligibility tracking (GPA, credits, dues)  
- Search, filtering, and CSV exports  
- Accessibility options such as zoom scaling and high-contrast mode  

This version loads **sample demo data** on first launch so the system can be explored right away. If you want to start fresh, the demo data can be cleared at any time through:

**File → Reset Database**

After resetting, the application is ready for real use.

### ▶ Run the Python GUI (from source)

**Requirements**
- Python 3.10+
- PySide6

**Install dependencies**
``bash
pip install -r python-gui/requirements.txt

**Run the app**
python python-gui/bandapp.py


## ⚙️ C++ Console Version (Systems Implementation)

This is a lighter, console-based version built in **C++ with SQLite integration**. It focuses more on database operations and the system-level side of the project rather than user interface features.

It is intentionally more minimal and serves as a lower-level implementation of the same core idea.

## Notes

This project functions as a working prototype and portfolio piece. The Python version represents the primary user experience, while the C++ version demonstrates systems-level understanding and cross-language architecture.

