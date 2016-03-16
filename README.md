rig-remote tim-devel-scan-thread notes
-------------------------------

This is a sub-branch from devel.

In this branch, we're implementing updating of scan parameters during an active scan. As part of that effort, additional input validation has been implemented.

Where we are now (15-Mar-2016): Input validation has been bolstered for scan parameters, and updates are successfully passed to the scan thread (which currently does nothing useful with them). Next up is to flesh out the update code in the scan thread.

