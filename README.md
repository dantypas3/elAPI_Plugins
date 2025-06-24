# elAPI Plugin Development – SFB 1638 Tools
This repository contains helper tools and plugin prototypes for extending the [elAPI framework](https://github.com/uhd-urz/elAPI), developed as part of the initiative **SFB 1638** at [Heidelberg University Biochemistry Center (BZH)](https://bzh.db-engine.de/)

These tools are designed to simplify resource interaction (e.g. patching metadata) and serve as early building blocks for elAPI plugins.

These tools are built on top of the official elAPI framework.

⚠️ Important: Make sure to follow the elAPI installation guide to configure your environment correctly before using these tools:

    https://github.com/uhd-urz/elAPI?tab=readme-ov-file#installation


### Important Points
* These tools rely on the external “elAPI” library. Installing that library and configuring API credentials
(as described in the upstream elAPI README) is required before these scripts can function.
* The utilities under utils/ wrap elAPI’s endpoints and provide validation helpers. Scripts in plugins/resources/ depend on these utilities.
* Files lack trailing newlines (the shell prompt appears after the last line when viewing them), but the code itself is intact.
* There are no tests or entry-point scripts; each module exposes functions (e.g., create_resources, patch_resources_from_csv) that can be imported or run from a small driver script.

### Where to go next

* Review the elAPI framework to understand the FixedEndpoint API and configuration.

* Look at patch_resources.py to see how resource metadata is expected to be structured—particularly the extra_fields handling.

* If you want to use these scripts, prepare CSV files matching the expected columns and ensure the API endpoint 
URLs/credentials are set up in your environment.

* The empty plugins/migration/labfolder.py indicates planned work; exploring the elAPI docs or contacting the authors
may clarify the intended migration functionality.