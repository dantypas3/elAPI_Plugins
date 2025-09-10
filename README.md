<h1 align="center">elAPI Plugin Development – SFB 1638 Tools</h1>
<p align="center">
  <img src="https://github.com/user-attachments/assets/e8ce314e-2f66-47af-9d08-b94324646984" alt="SFB1638 Logo" width="200">
</p>


This repository contains helper tools and plugin prototypes for extending
the [elAPI framework](https://github.com/uhd-urz/elAPI).  
elAPI Plugins are being developed as part of the INF Project of the **CRC 1638** at
the [Heidelberg University Biochemistry Center (BZH)](https://bzh.db-engine.de/).

These tools are designed to simplify resource interaction (e.g., patching metadata) and serve as early building blocks
for elAPI plugins.  
They are built on top of the official elAPI framework.

---

## Prerequisites

- [elAPI](https://github.com/uhd-urz/elAPI?tab=readme-ov-file#installation) must be installed and initialized with a
  valid elabFTW API key.
- Follow the elAPI [installation guide](https://github.com/uhd-urz/elAPI?tab=readme-ov-file#installation) to configure
  your environment correctly before using these tools.

---

## Important Notes

- These tools depend on the external **elAPI** library. Install that library and configure API credentials as described
  in the elAPI README.
- The utilities under `utils/` wrap elAPI’s endpoints and provide validation helpers. Scripts in `plugins/resources/`
  depend on these utilities.
- Files may lack trailing newlines (which may cause the shell prompt to appear immediately after the last line), but the
  code itself is intact.
- There are no tests or entry-point scripts; each module exposes functions (e.g., `create_resources`,
  `patch_resources_from_csv`) that can be imported or run from a small driver script.

---

## Running the Export GUI

The repository provides helper scripts for starting `gui.gui` in a fresh virtual environment. Ensure Python 3.12 or
later is installed.  
These scripts automatically check for a configured API token and, if none is found, launch `elapi init`.
> **Note:** elAPI must be installed as described above.

### macOS

Double-click `run_gui.command` from the repository root or run it from Terminal. The script will:

1. Create a `venv` directory
2. Install the dependencies from `requirements.txt`
3. Ensure an API token is configured (runs `elapi init` if needed)
4. Launch `gui.gui`

### Windows

Double-click `run_gui_hidden.vbs` or run it from a terminal. This wrapper calls `run_gui.bat`, which will:

1. Create the virtual environment
2. Install dependencies
3. Check for an API token (runs `elapi init` if necessary)
4. Launch the export GUI

---

## Navigating to the Repository Directory (For Beginners)

If you're not familiar with the command line, follow these steps:

1. **Open a Terminal / Command Prompt**
    - **macOS/Linux:** Open the *Terminal* app
    - **Windows:** Press `Windows + R`, type `cmd`, and press Enter

2. **Find the Repository Path**  
   Locate the folder where you downloaded or cloned this repository.
    - **macOS:** Right-click → “Get Info” → copy the full path
    - **Windows:** Shift + right-click → “Copy as path”

3. **Use `cd` to Navigate**  
   In the terminal, type `cd` followed by the path:  
   **macOS example:**
     ```bash
     cd /Users/yourusername/Downloads/elAPI_Plugins
     ```  
   **Windows example:**
     ```cmd
     cd "C:\Users\YourName\Downloads\elAPI_Plugins"
     ```

4. **Confirm You’re in the Right Folder**  
   **macOS/Linux**
   ```bash
      ls
     ```
   **Windows**
    ```bash
      dir  
   ```  
   You should see:
   ```
   run_gui.command
   requirements.txt
   plugins/
   utils/
   ```

5. **Run the GUI Launcher**  
   **macOS:**
     ```bash
     ./run_gui.command
     ```  
   **Windows:**
     ```bash
     ./run_gui.vbs
     ```

---

## Important Note for macOS Users (Permissions)

If execution is blocked:

1. Open **System Settings → Privacy & Security**
2. Scroll down to the **Security** section and allow the blocked script
3. In Terminal, run:
   ```bash
   sudo chmod +x run_gui.command
   ```  
4. Re-run the launcher:
   ```bash
   ./run_gui.command
   ```

---

## Where to Go Next

- Review the [elAPI framework](https://github.com/uhd-urz/elAPI) to understand how the FixedEndpoint API works and how
  to configure it.
- Prepare CSV files with the expected columns and ensure your environment is set up with the correct API endpoint URLs
  and credentials.
