##############################################################################
## Synthesis IP hierarchy constraints: customize before building.
## Replace example_ip with the actual IP module/reference name, then uncomment
## the assignment. Add one explicit assignment for each intended IP reference.
## Check that the query matches the intended instances in your design.
## KEEP_HIERARCHY SOFT is a synthesis choice, not required for every IP.
##############################################################################
# set_property KEEP_HIERARCHY SOFT [get_cells -hier -filter {REF_NAME == example_ip || ORIG_REF_NAME == example_ip}]
