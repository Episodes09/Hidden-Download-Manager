# Hidden-Download-Manager
A compact and persistent floating multi-download manager for Windows built with Python. Features background download processing, global shortcut visibility controls (Win+Shift+H), live tracking analytics (MB left, percentage, current speed), customizable UI, a sequential auto-processing queue pipeline, and absolute workspace memory recovery.
# ☰ Hidden-Download-Manager 🚫

A stealthy, persistent, and modular floating multi-download widget engineered for high-performance sequential background operations. Fully customizable with custom dark/light UI profiles, automatic directory cleanup loops, an active job queue, and global background hotkey event hooks.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-brightgreen?style=for-the-badge&logo=opensourceinitiative&logoColor=white)

---

## ✨ Features

* **Stealth Minimization Mode:** Collapse the window completely to clean up desktop real estate. The downloader runs silently in the background without populating your taskbar window lists.
* **Global Hotkey Recovery:** Tap **`Win + Shift + H`** universally from any program or full-screen application to instantly pop the downloader right back to the front.
* **Smart Interruption Recovery:** If your network cuts out, your computer crashes, or you quit out prematurely, your exact position and URL sequence are saved to an isolated local data block. Simply launch the app again to continue exactly where you left off.
* **Automated File Operations:** Automatically drops network buffers, appends data directly into active `.part` streams, verifies integrity upon completion, clears localized workspace `.json`/temp metadata caches, and rolls right onto the next task in the queue.
* **Advanced Real-Time Metrics:** Live analytics displaying current throughput rate (`MB/s`), total volume remaining (`MB Left`), and task completion indexes (`%`).
* **Multi-Job Queue Pipeline:** Right-click anywhere on the canvas to open the *Queue Manager* panel where you can seamlessly stage long lists of downloads to run sequentially.
* **Theming Profiles:** Switch effortlessly via settings between a striking dark cyberpunk profile and a functional classic light mode.

---

## 🛠️ Installation & Setup

### Prerequisites
Ensure you have **Python 3.8 or higher** installed on your Windows machine, then open your terminal and install the required global listener module dependency:

```bash
pip install requests keyboard
