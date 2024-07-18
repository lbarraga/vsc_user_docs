# Conda

We do not recommend the use of conda environments on the HPC clusters. 
This section explains why and highlights some common issues.

## Performance and Optimization

Conda packages are pre-compiled binaries that are designed to work on a wide range of systems. 
This means they are not optimized for the specific architecture of HPC clusters, 
leading to potential performance drawbacks compared to modules compiled specifically for the HPC environment.

HPC modules on the other hand, are compiled for the specific architecture of the cluster,
and are optimized for performance.

## Compatibility and Dependency

Using Conda in conjunction with centrally installed modules can lead to conflicts and unexpected errors, 
making it difficult to debug and manage dependencies.

## Package Availability

Conda has a smaller repository of available packages compared to PyPI, the repository used by pip. 
This can limit the availability of specific tools or libraries needed for certain workflows.

## Environment and Installation Issues

### Home Directory Usage

Conda installs packages and environments in the user's home directory, 
which can quickly fill up disk quotas due to the large number of files and directories it creates. 
This is particularly problematic in HPC environments where home directory quotas are often limited.

### Modification of Configuration Files

Conda modifies the .bashrc file in the user's home directory, 
which can lead to conflicts and unintended side effects in the user's environment setup.