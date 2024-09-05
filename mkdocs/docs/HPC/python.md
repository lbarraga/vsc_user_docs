# Python 

This page explains how to use Python on the HPC systems using only centrally installed modules. 
If you would like to use Python packages that are not available as a module,
check out the [Python Virtual Environments](./setting_up_python_virtual_environments.md) page.

## Using Python with only standard library packages

To run a Python script that only uses the standard library (os, sys, math, etc.), only a Python module is required.

HPC clusters provide multiple versions of Python via the environment modules. 
To see which Python versions are available, run:

```bash
module avail Python
```

Once you've identified the version you want, you can load it as follows:

```bash
module load Python/3.10.8-GCCcore-12.2.0  # Load a specific version of Python
```

To ensure the module is loaded correctly, check the Python version:

```bash
python --version  # Verify Python version
Python 3.10.8
```

Let's consider an example script `script.py` that prints the square root of 2:

```python title="script.py"
import math

print(math.sqrt(2))
```

The script can be executed using the loaded Python module:

```bash
$ python example.py
```

## Using python with non-standard library packages

If your python script requires non-standard library packages (e.g., numpy, pandas, ...), 
you will need to load these packages via modules. 
Most of these modules already come with a specific python module.
It is therefore not necessary to load the python module separately.

To search for a specific package, you can use the `module avail` command. For example:

```bash
$ module avail beautifulsoup  # Search for the BeautifulSoup Python package
```

If the package is available, you can load it using the `module load` command.
For example, to load the `beautifulsoup` module, you can use:

```bash
$ module load BeautifulSoup/4.11.1-GCCcore-12.2.0
```

This will also load a Python module.

Some Python packages are installed as extensions of modules. 
For example, `numpy`, `scipy` and `pandas` are part of the `SciPy-bundle` module. 

You can use

```bash
module show module_name
```

to check which extensions are included in a module (if any).

Consider the following example script `script.py` that uses the `numpy` package:

```python title="script.py"
import numpy as np
```


## Submitting a Python script to a cluster using a job script

Let's say we want to run the following script on the `doduo` cluster:

```python title="script.py"
import numpy

print(numpy.sqrt(2))
```

We create a job script `job.pbs` that loads the required module and runs the script.
Because numpy is not part of the standard library, we need to load the `SciPy-bundle` module before running the script.

```bash title="job.pbs"
#!/bin/bash

# Basic parameters
#PBS -N python_job_example                    ## Job name
#PBS -l nodes=1:ppn=1                         ## 1 node, 1 processor per node
#PBS -l walltime=01:00:00                     ## Max time your job will run (no more than 72:00:00)

module load SciPy-bundle/2023.11-gfbf-2023b   # Load the SciPy-bundle module
cd $PBS_O_WORKDIR                             # Change working directory to the location where the job was submitted

python script.py                              # Run your Python script
```

Before we submit the job, we swap the cluster to `doduo`:

```bash
$ module swap cluster/doduo
```

Now we can submit the job:

```bash
$ qsub job.pbs
```

After some time, two files will be created in the directory where the job was submitted: 
`python_job_example.o{{jobid}}` and `python_job_example.e{{job_id}}`, where {{jobid}} is the id of your job.
The `.o` file contains the output of the job.
