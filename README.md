<h1 align="center">elAPI Plugin Development – SFB 1638 Tools</h1>
<p align="center">
  <img src="https://github.com/user-attachments/assets/e8ce314e-2f66-47af-9d08-b94324646984" alt="SFB1638 Logo" width="200">
</p>

This repository contains helper tools and plugin prototypes for extending the [elAPI framework](https://github.com/uhd-urz/elAPI). elAPI Plugins are being
developed as part of the INF Project of the **CRC 1638** at [Heidelberg University Biochemistry Center (BZH)](https://bzh.db-engine.de/)

These tools are designed to simplify resource interaction (e.g. patching metadata) and serve as early building blocks for elAPI plugins.

These tools are built on top of the official elAPI framework.

### Prerequisites
* [elAPI](https://github.com/uhd-urz/elAPI?tab=readme-ov-file#installation) should be installed and initialised with
a valid elabFTW API key. Make sure to follow the elAPI [installation guide](https://github.com/uhd-urz/elAPI?tab=readme-ov-file#installation)
to configure your environment correctly before using these tools.

### Important Points
* These tools rely on the external “elAPI” library. Installing that library and configuring API credentials
(as described in the upstream elAPI README) is required before these scripts can function.
* The utilities under utils/ wrap elAPI’s endpoints and provide validation helpers. Scripts in plugins/resources/ depend
on these utilities.
* Files lack trailing newlines (the shell prompt appears after the last line when viewing them), but the code itself is intact.
* There are no tests or entry-point scripts; each module exposes functions (e.g., create_resources, patch_resources_from_csv)
that can be imported or run from a small driver script.

### Running the export GUI
The repository provides helper scripts for starting `gui.gui` in a fresh
virtual environment. Ensure Python 3.12 or later is installed and that elAPI is configured as
described in the prerequisites above.

#### macOS / Linux

Double click `run_gui.command` from the repository root or execute it from a Terminal. The script creates a `venv` directory,
installs `requirements.txt`, and then launches `gui.gui`.
##### Important Note for MacOS Users:
* Open System Settings → Privacy & Security
* Scroll down to the Security section and allow the application/script when prompted.
* Open a terminal, navigate to the directory containing this repository, and run:
```sudo chmod +x run_gui.command```.  
This ensures the script is executable by the system.

#### Windows

Double click `run_gui_hidden.vbs` or execute it from a Terminal. It performs the same setup steps and launches the
export GUI

### Navigating to the Repository Directory (for Beginners)

If you're not familiar with using the command line, here's how you can navigate to the folder containing this repository using the cd (change directory) command.
Step-by-step:

1. Open a Terminal / Command Prompt:

    * macOS/Linux: Open the Terminal application.

    *    Windows: Press Windows + R, type cmd, and press Enter.

1. Find the Path to the Repository Folder:

   Locate the folder where you downloaded or cloned this repository using your file manager.
   Right-click the folder and:

    * macOS/Linux: Select "Get Info" or "Properties" and copy the full path.

    * Windows: Hold Shift and right-click the folder, then choose "Copy as path".

1. Use the cd Command to Navigate:

    In the terminal, type cd (with a space), then paste the folder path.

    * Example for macOS/Linux:

    `cd /Users/yourusername/Downloads/elAPI_Plugins`

    * Example for Windows:

    `cd "C:\Users\YourName\Downloads\elAPI_Plugins"`

    On Windows, make sure the path is in double quotes if it contains spaces.

1. Confirm You're in the Right Place:

    Type `ls` (macOS/Linux) or `dir` (Windows) to list the contents of the folder. You should see files like run_gui.command,
   requirements.txt, and folders like plugins/ and utils/.

### Where to go next

* Review the elAPI framework to understand the FixedEndpoint API and configuration.

* Look at `plugins/resources/patch.py` to see how resource metadata is expected to be structured—particularly the `extra_fields` handling.

* If you want to use these scripts, prepare CSV files matching the expected columns and ensure the API endpoint 
URLs/credentials are set up in your environment.