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
The repository provides helper scripts for starting `plugins.resources.export_gui` in a fresh
virtual environment. Ensure Python 3.12 or later is installed and that elAPI is configured as
described in the prerequisites above.

#### macOS / Linux

Run `./run_gui.command` from the repository root. The script creates a `venv` directory,
installs `requirements.txt`, and then launches `gui.gui`.
##### Important Note for MacOS Users:
* Open System Settings → Privacy & Security
* Scroll down to the Security section and allow the application/script when prompted.
* Open a terminal, navigate to the directory containing this repository, and run:
```sudo chmod +x run_gui.command```.  
This ensures the script is executable by the system.

#### Windows

Run `run_export.bat` from a Command Prompt. It performs the same setup steps and launches the
export GUI

### Where to go next

* Review the elAPI framework to understand the FixedEndpoint API and configuration.

* Look at patch_resources.py to see how resource metadata is expected to be structured—particularly the extra_fields handling.

* If you want to use these scripts, prepare CSV files matching the expected columns and ensure the API endpoint 
URLs/credentials are set up in your environment.

* The empty plugins/migration/labfolder.py indicates planned work; exploring the elAPI docs or contacting the authors
may clarify the intended migration functionality.
