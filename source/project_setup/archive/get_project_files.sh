#tool_box: <project.xpr>; Extract and normalize user-added Vivado source files with $REPO_TOP replacement
vivado -mode tcl -source $REPO_TOP/tools/project_setup/get_project_files.tcl -tclargs $1 \
| grep "vivado_file:/" \
| sed "s|vivado_file:||" \
| sed "s|$REPO_TOP|\\\$REPO_TOP|g"
