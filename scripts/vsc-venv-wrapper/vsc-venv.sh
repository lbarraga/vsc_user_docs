SCRIPT_NAME=$(basename "${BASH_SOURCE[0]}") # $0 cannot be used as it gives '-bash' when sourced
VERSION="1.0.6"

usage() {
  echo "Usage: source $SCRIPT_NAME {-a | --activate -r | --requirements <requirements.txt> [-m | --modules <modules.txt>]} | {-d | --deactivate} [-h | --help] [-v | --version]"
  echo ""
  echo "Commands:"
  echo "  -a, --activate          Activate the environment."
  echo "    -r, --requirements    (Required) Specify the requirements file (e.g., requirements.txt)."
  echo "    -m, --modules         (Optional) Specify a modules file (e.g., modules.txt)."
  echo ""
  echo "  -d, --deactivate        Deactivate the virtual environment."
  echo ""
  echo "  -h, --help              Show this help message and exit."
  echo "  -v, --version           Show the version information and exit."
  echo ""
  echo "Example Usage:"
  echo "  $ source $SCRIPT_NAME --activate --requirements requirements.txt --modules modules.txt"
  echo "  $ python my_script.py"
  echo "  $ source $SCRIPT_NAME --deactivate"
}


echo_info() { echo -e "\e[32m$SCRIPT_NAME: [INFO] $1\e[0m"; }
echo_warning() { echo -e "\e[33m$SCRIPT_NAME: [WARNING] $1\e[0m"; }
echo_error() { echo -e "\e[31m$SCRIPT_NAME: [ERROR] $1\e[0m"; }

load_modules() {
  local modules_file lines
  modules_file="$1"

  if ! mapfile -t lines < "$modules_file"; then # Read the file line by line into an array
    echo_error "Could not read modules script '$modules_file'"
    return 1
  fi

  for line in "${lines[@]}"; do # Loop over each line in the array

    # Skip empty lines
    if [[ -z "$line" ]]; then
      continue
    fi

    if module load $line; then
      echo_info "  ✔ Module '$line' loaded successfully"
    else
      echo_error "Could not load module '$line'"
      return 1
    fi

  done

}

# Description:
#   This function checks if the currently loaded cluster's operating system and architecture are the same
#   as the current host's OS and architecture.
#   For example, switching to the shinx cluster on a gallade host will create a mismatch
#   (RHEL8-zen2 on gligar and RHEL9-zen4 on shinx at the time of writing)
#
# Return:
#   0 (true) - If the loaded cluster's OS and architecture match the host's OS and architecture.
#   1 (false) - If there is a mismatch between the loaded and current host's OS or architecture.
is_loaded_cluster_compatible_with_host() {
  local loaded_cluster_os loaded_cluster_architecture
  local current_host_os current_host_architecture

  loaded_cluster_os="$VSC_OS_LOCAL"
  loaded_cluster_architecture="$VSC_ARCH_LOCAL"

  current_host_os=$(ml show env/vsc/"$VSC_DEFAULT_CLUSTER_MODULE" | grep VSC_OS_LOCAL | cut -d'"' -f4)
  current_host_architecture=$(ml show env/vsc/"$VSC_DEFAULT_CLUSTER_MODULE" | grep VSC_ARCH_LOCAL | cut -d'"' -f4)

  if [ "$loaded_cluster_os-$loaded_cluster_architecture" = "$current_host_os-$current_host_architecture" ]; then
    return 0
  else
    return 1
  fi
}

module_purge_keep_vsc_venv() {
  vsc_venv_module=$(echo "$LOADEDMODULES" | tr ':' '\n' | grep ^vsc-venv/)

  echo_info "Purging currently loaded modules."
  module purge

  if [ ! -z ${vsc_venv_module} ]; then
      module load ${vsc_venv_module}
  fi
}


# ============================ Main functions ============================

activate() {
  local requirements_file modules_file
  local venv_location n_loaded_modules python_version

  requirements_file="$1"
  modules_file="$2"

  venv_location=$(realpath -m "venvs/venv-${VSC_OS_LOCAL}-${VSC_ARCH_LOCAL}") # full path of venv

  # === Check if requirements file exists === #
  if [ ! -f "$requirements_file" ]; then
    echo_error "Requirements file '$requirements_file' not found, use --requirements or -r to specify correct path"
    return 1
  fi

  # === Warn users if os-arch of current host and loaded module do not match === #
  if ! is_loaded_cluster_compatible_with_host; then
    local loaded_cluster="$VSC_INSTITUTE_CLUSTER"
    local host_cluster="$VSC_DEFAULT_CLUSTER_MODULE"
    echo_warning "The OS or architecture of the current host ($host_cluster) does not match that of the loaded cluster ($loaded_cluster)."
    echo_warning "Creating or activating a virtual environment on $host_cluster with modules optimized for $loaded_cluster may cause issues."
    echo_warning "to make a virtual environment on the $loaded_cluster cluster, start an interactive session on that cluster:"
    echo_warning "  $ qsub -I"
    echo_warning "  $ cd /path/to/your/project"
    echo_warning "Then run the activate command again."
    echo_warning "Exiting..."
    return 1
  fi

  # === Warn user if they have a virtual environment activated === #

  if [ -n "$VIRTUAL_ENV" ]; then
    echo_warning "You already have a virtual environment activated."
    echo_warning "This virtual environment will be deactivated."
    deactivate_
  fi

  # === Warn user if they have modules loaded === #
  loaded_modules=($(echo "$LOADEDMODULES" | tr ':' '\n' | grep -v -E '^(env|cluster|vsc-venv)/')) # Remove env, cluster and vsc-venv modules
  n_loaded_modules="${#loaded_modules[@]}"
  if [ "$n_loaded_modules" -gt 0 ]; then
    echo_warning "You have $n_loaded_modules loaded modules in the current shell. These modules will be purged."
    echo_warning "If you want to use these modules, please provide a modules file listing the required modules using the --modules or -m flag."

    echo_info "Purging currently loaded modules."
    module_purge_keep_vsc_venv
  fi

  # === Load Modules if module script present === #

  if [ -n "$modules_file" ]; then # If module script not empty

    echo_info "Loading modules from '$modules_file'"

    if ! load_modules "$modules_file"; then # If the modules could not be loaded
      echo_error "Could not load modules from '$modules_file'"
      return 1
    fi

    echo_info "Modules loaded successfully"

  else
    echo_info "No module file provided. Proceeding without extra modules."
  fi

  # === Create Virtual Environment if not yet present === #

  # Warn user if system python is used
  if [ "$(which python)" = "/usr/bin/python" ]; then
    echo_warning "System python used. Consider loading a specific Python module through the modules file."
  fi

  # Check if venv already exists
  if [ -f "$venv_location/bin/activate" ]; then
    # The virtual environment already exists
    echo_info "Virtual environment already exists at $venv_location"

    # Warn user if a different python module is loaded than the one used to create the virtual environment
    local current_python venv_python
    current_python=$(realpath "$(which python)")
    venv_python=$(realpath -m "$venv_location/bin/python")

    if [ "$current_python" != "$venv_python" ]; then
      echo_error "The python module used to create the virtual environment is different from the one currently loaded."
      echo_error "Current python module:  $current_python"
      echo_error "venv python module:     $venv_python"
      echo_error "If you changed the python module in $modules_file,"
      echo_error "please remove the virtual environment that uses the old python with the following command:"
      echo_error "  $ rm -rf $venv_location"
      echo_error "After removing the virtual environment, run the activate command again."
      echo_error "Exiting..."
      return 1
    fi

  else
    # The virtual environment does not exist
    echo_info "Virtual environment does not exist at $venv_location"
    python_version=$(python --version)
    echo_info "Using $python_version to create virtual environment at $venv_location"

    # Will automatically make the venvs folder and venv, does nothing if they already exist
    if ! python -m venv "$venv_location"; then
      echo_error "Could not create virtual environment"
      return 1
    fi
  fi

  # === Activate Virtual Environment === #

  echo_info "Activating virtual environment"
  source "$venv_location/bin/activate"

  # === Warn user if requirements contain lines without version specifiers === #
  local version_specifiers="==|>=|<=|!=|<|>|~="
  local lines_without_versions=$(grep -vE "$version_specifiers" "$requirements_file")

  # Check if the variable is not empty
  if [ -n "$lines_without_versions" ]; then
      echo_warning "The following lines do not contain version specifiers:"
      echo_warning "$lines_without_versions"
  fi


  # === Install Requirements === #

  echo_info "Installing requirements from '$requirements_file'"
  if ! pip install -r "$requirements_file"; then # This will finish quickly if the requirements are already installed
    echo_error "Could not install requirements"
    deactivate
    return 1
  fi

  echo_info "Requirements installed successfully"
  echo_info "You can now run your Python scripts"
}

deactivate_() {
  echo_info "Deactivating virtual environment at $VIRTUAL_ENV"
  deactivate # For now, just use the python `deactivate`
  echo_info "Purging loaded modules"
  module_purge_keep_vsc_venv
}

unknown_action() {
  echo_error "Unknown action"
  usage
  return 1
}

help() {
  usage
  return 0
}

version() {
  echo "$SCRIPT_NAME v${VERSION}"
  return 0
}

# ============================ Main ============================

ACTION="UNKNOWN"
MODULES=""
REQUIREMENTS=""
while [ $# -gt 0 ] ; do
  case $1 in
    -a | --activate)      ACTION="activate" ;;
    -d | --deactivate)    ACTION="deactivate" ;;
    -h | --help)          ACTION="help" ;;
    -m | --modules)       MODULES="$2" ;;
    -r | --requirements)  REQUIREMENTS="$2" ;;
    -v | --version)       ACTION="version";;
  esac
  shift
done

# This script must be sourced for activating and deactivating the virtual environment
if { [[ "$ACTION" == "activate" || "$ACTION" == "deactivate" ]] && [[ "${BASH_SOURCE[0]}" == "${0}" ]]; }; then
    echo_error "This script must be sourced! Check the usage with 'source $SCRIPT_NAME --help'"
    exit 1
fi

case "$ACTION" in
  activate)    activate "$REQUIREMENTS" "$MODULES";;
  deactivate)  deactivate_ ;;
  help)        help ;;
  version)     version ;;
  *)           unknown_action ;;
esac
