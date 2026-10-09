# SwipeAI 🚀

**SwipeAI** is an autonomous agentic pipeline designed to perform automated vetting and swiping on dating applications (prototyped on Facebook Dating) using computer vision and local Large Language Models (LLMs).

The project demonstrates a complete end-to-end loop: from screen capture and OCR to rule-based filtering and intelligent, LLM-driven decision-making.

---

## ✨ Key Features

* **🤖 Agentic Decision Making**: Uses a local vision-capable LLM (e.g., Gemma/Llama via llama.cpp) to evaluate profile photos and bios against complex personal preferences.
* **👁️ Computer Vision Pipeline**:
    * **Template Matching**: High-precision button and layout detection using OpenCV.
    * **Face Detection**: Integrated YuNet (and Haar cascade fallback) for ensuring profile authenticity.
    * **OCR**: Robust text extraction (Name, Age, Bio) using Tesseract.
* **⚖️ Multi-Stage Vetting**:
    1. **Rule-Based Filtering**: Fast, local checks for age range, face presence, and image quality (brightness/sharpness).
    2. **LLM Evaluation**: Deep reasoning for aesthetic and bio-based preferences.
* **🛠️ Robust Automation**: Fully controlled via ADB (Android Debug Bridge) on Waydroid/Android emulators.
* **📦 Nix-Powered**: Reproducible development environment using Nix.

## 🏗️ Architecture

The pipeline operates in a continuous loop:
1. **Capture**: Screen capture from the Android device.
2. **Detect**: Detect UI layouts (Card vs. Profile view) and interaction buttons.
3. **Extract**: Parse text (Name, Age, Bio) and detect faces.
4. **Vet**:
   - Apply hard rules (e.g., age, image quality).
   - If rules pass, send visual + text data to the local LLM.
5. **Act**: Execute a tap (LIKE/DISLIKE/SKIP) via ADB.
6. **Log**: Record decision reasoning and summary data.

## 🚀 Tech Stack

* **Language**: Python
* **Environment**: Nix / Nix-shell
* **Automation**: ADB (Android Debug Bridge)
* **Computer Vision**: OpenCV, YuNet, Tesseract OCR
* **LLM Inference**: `llama.cpp` (OpenAI-compatible API)
* **Emulator**: Waydroid (Android 13)

## 🛠️ Installation & Setup

### Prerequisites
* [Nix](https://nixos.org/)
* [ADB](https://developer.android.com/studio/command-line/adb)
* An Android device or emulator (e.g., Waydroid) running Facebook Dating.
* A local LLM server (e.g., `llama.cpp` serving a vision model).

### Waydroid (manual setup)
The script does **not** start the Waydroid container (it needs root). If you use Waydroid, start it yourself before running the workflow:
```bash
sudo waydroid container start
waydroid session start            # needs a graphical session
waydroid status                   # Container should be RUNNING, not FROZEN
adb connect <ADB_DEVICE>          # e.g. 192.168.240.112:5555
```
Then set `WAYDROID_MODE=1` in `.env`. With this set, the script checks for the device, starts the session if it is not running, and waits up to 30 seconds for ADB. If the device still isn't ready it exits with an error. Set `WAYDROID_MODE=0` for a physical phone or emulator you manage yourself.

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/SwipeAI.git
   cd SwipeAI
   ```
2. Enter the development environment:
   ```bash
   nix-shell
   ```
3. Run a dry run (vets 1 profile without tapping):
   ```bash
   ./workflow_script.sh
   ```
4. Start swiping (e.g., 10 profiles):
   ```bash
   ./workflow_script.sh --swipe -n 10
   ```

## ⚠️ Disclaimer

**This project is for educational and research purposes only.** 

Automated interaction with dating platforms may violate their Terms of Service. The authors are not responsible for any actions taken by users of this software. Use at your own risk.

## 📄 License

This project is licensed under the [MIT License](LICENSE).
