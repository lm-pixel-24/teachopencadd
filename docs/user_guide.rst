User guide
==========

.. note::

    We are assuming you have a working ``conda`` installation on your computer. 
    If this is not the case, please refer to the `official documentation <https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html>`_. 


Run Locally
-----------

.. note::

    To set up the project on your machine, follow these steps:

1. **Clone the repository:**
   Open your terminal and clone the repository:

   .. code-block:: bash

       git clone https://github.com/volkamerlab/teachopencadd.git
       cd teachopencadd

2. **Execute notebooks:**
   Inside the main directory, run the following command (please ensure you have ``conda`` installed).

   .. code-block:: bash

       python main.py -t T001

   Here ``T001`` is the ID referring to the talktorial to execute.

   It will take a couple of minutes if you're running a particular notebook for the very first time. First, the system will internally create a Conda virtual environment and install all necessary Python packages; you can monitor the progress logs in the terminal. Then, the notebook will launch in your browser.