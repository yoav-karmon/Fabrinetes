# Bash completion script for hdlforge
# Source this file in your .bashrc: source /path/to/hdlforge_completion.bash
# Or install to /etc/bash_completion.d/hdlforge

_hdlforge_completions() {
    local cur prev words cword
    _init_completion || return

    # All words in the command line
    local all_words="${COMP_WORDS[*]}"

    # Available tools
    local tools="vivado verilator network vcd_analyzer tsharkWrapper hw_server projects"

    # Network commands
    local network_cmds="send_raw send_arp send_icmp send_udp"

    # hw_server commands
    local hw_server_cmds="program scan_ila scan_jtag read_dna"

    # Network command-specific parameters
    local network_send_raw_params="--interface --data --verbose"
    local network_send_arp_params="--interface --arp_op --eth_dst_mac --eth_src_mac --src_mac --src_ip --dst_mac --dst_ip --verbose"
    local network_send_icmp_params="--interface --eth_dst_mac --eth_src_mac --src_ip --dst_ip --icmp_type --icmp_code --identifier --sequence --data --verbose"
    local network_send_udp_params="--interface --eth_dst_mac --eth_src_mac --src_ip --dst_ip --src_port --dst_port --data --verbose"

    # Vivado steps (--step is deprecated, use direct flags like --syn, --impl, --bit)
    local vivado_steps="syn impl bit all lint list_runs reset_run generate_prj_with_external_tcl write_tcl file_remove file_add clean_logs"

    # Verilator operations
    local verilator_ops="build sim clean"

    # Common flags
    local common_flags="--project --tool --verbose --help"

    # Helper function to check if a word exists in the command line
    _word_in_args() {
        local word="$1"
        for w in "${COMP_WORDS[@]}"; do
            [[ "$w" == "$word" ]] && return 0
        done
        return 1
    }

    # Helper function to get the value after a specific flag
    _get_flag_value() {
        local flag="$1"
        for ((i=1; i < ${#COMP_WORDS[@]}; i++)); do
            if [[ "${COMP_WORDS[i]}" == "$flag" && $((i+1)) -lt ${#COMP_WORDS[@]} ]]; then
                echo "${COMP_WORDS[i+1]}"
                return
            fi
        done
    }

    # Check what context we're in
    case "$prev" in
        hdlforge)
            # After hdlforge, suggest --tool only
            COMPREPLY=($(compgen -W "--tool" -- "$cur"))
            return
            ;;
        --tool)
            # After --tool, suggest available tools
            COMPREPLY=($(compgen -W "$tools" -- "$cur"))
            return
            ;;
        --project)
            # After --project, suggest .hdlforge.json or .hdlforge.toml files
            COMPREPLY=($(compgen -f -X '!*.hdlforge.@(json|toml)' -- "$cur"))
            compopt -o filenames 2>/dev/null
            return
            ;;
        --cmd)
            # After --cmd, suggest commands based on selected tool
            local tool=$(_get_flag_value "--tool")
            if [[ "$tool" == "network" ]]; then
                COMPREPLY=($(compgen -W "$network_cmds" -- "$cur"))
            elif [[ "$tool" == "hw_server" ]]; then
                COMPREPLY=($(compgen -W "$hw_server_cmds" -- "$cur"))
            else
                # If tool not yet selected, suggest all commands
                COMPREPLY=($(compgen -W "$network_cmds $hw_server_cmds" -- "$cur"))
            fi
            return
            ;;
        --interface)
            # After --interface, suggest network interfaces
            local interfaces=$(ip -o link show 2>/dev/null | awk -F': ' '{print $2}' | cut -d'@' -f1)
            COMPREPLY=($(compgen -W "$interfaces" -- "$cur"))
            return
            ;;
        --arp_op)
            # ARP operation: 1=request, 2=reply
            COMPREPLY=($(compgen -W "1 2" -- "$cur"))
            return
            ;;
        --icmp_type)
            # ICMP type: 8=echo request, 0=echo reply
            COMPREPLY=($(compgen -W "0 8" -- "$cur"))
            return
            ;;
        --icmp_code)
            # ICMP code (usually 0)
            COMPREPLY=($(compgen -W "0" -- "$cur"))
            return
            ;;
        --vcdfilename)
            # After --vcdfilename, suggest files and directories for navigation
            COMPREPLY=($(compgen -f -- "$cur"))
            compopt -o filenames 2>/dev/null
            return
            ;;
        --get_values_pins|--get_values_all)
            # After --get_values_pins or --get_values_all, user needs to type module path - no completion
            return
            ;;
        --src_ip|--dst_ip)
            # Suggest common IP patterns
            COMPREPLY=($(compgen -W "192.168.1.1 192.168.1.2 192.168.1.100" -- "$cur"))
            return
            ;;
        --src_mac|--dst_mac|--eth_src_mac|--eth_dst_mac)
            # Suggest broadcast MAC or placeholder
            COMPREPLY=($(compgen -W "FF:FF:FF:FF:FF:FF 00:00:00:00:00:00" -- "$cur"))
            return
            ;;
        --src_port|--dst_port)
            # Suggest common ports
            COMPREPLY=($(compgen -W "53 80 443 8080 12345" -- "$cur"))
            return
            ;;
        --identifier|--sequence)
            # Suggest 0 as default
            COMPREPLY=($(compgen -W "0 1" -- "$cur"))
            return
            ;;
        --data)
            # Hex data - no completion, but show hint
            return
            ;;
        --step)
            # Vivado steps (deprecated for vivado, used by verilator)
            local tool=$(_get_flag_value "--tool")
            if [[ "$tool" == "verilator" || "$tool" == "Verilator" ]]; then
                COMPREPLY=($(compgen -W "build sim" -- "$cur"))
            fi
            return
            ;;
        --syn|--impl|--bit|--all|--reset_run)
            # Vivado run names - try to get from project file
            local project_file=$(_get_flag_value "--project")
            if [[ -z "$project_file" ]]; then
                project_file=$(ls *.hdlforge.json 2>/dev/null | head -1)
            fi
            if [[ -n "$project_file" && -f "$project_file" ]]; then
                # Try to get synth run names from JSON
                local runs=$(jq -r '.vivado.config.runs_flow // [] | .[].synth_run // empty' "$project_file" 2>/dev/null | sort -u)
                if [[ -n "$runs" ]]; then
                    COMPREPLY=($(compgen -W "$runs" -- "$cur"))
                fi
            fi
            return
            ;;
        --sim_target|--SimTargetName)
            # Try to find sim targets from project file
            local project_file=$(_get_flag_value "--project")
            # If no --project, try to find .hdlforge.json in current dir
            if [[ -z "$project_file" ]]; then
                project_file=$(ls *.hdlforge.json 2>/dev/null | head -1)
            fi
            if [[ -n "$project_file" && -f "$project_file" ]]; then
                local targets=$(jq -r '.verilator.sim_targets | keys[]' "$project_file" 2>/dev/null)
                COMPREPLY=($(compgen -W "$targets" -- "$cur"))
            fi
            return
            ;;
        --pcap)
            # After --pcap, suggest .pcap files and directories
            COMPREPLY=($(compgen -f -- "$cur"))
            compopt -o filenames 2>/dev/null
            return
            ;;
        --bitstream)
            # After --bitstream, suggest .bit files and directories
            COMPREPLY=($(compgen -f -- "$cur"))
            compopt -o filenames 2>/dev/null
            return
            ;;
        --probes)
            # After --probes, suggest .ltx files and directories
            COMPREPLY=($(compgen -f -- "$cur"))
            compopt -o filenames 2>/dev/null
            return
            ;;
        --hw-config|-c)
            # After --hw-config or -c, suggest .json files and directories
            COMPREPLY=($(compgen -f -- "$cur"))
            compopt -o filenames 2>/dev/null
            return
            ;;
        --server_ip)
            # Suggest common server IPs
            COMPREPLY=($(compgen -W "10.1.130.74 192.168.1.100 localhost" -- "$cur"))
            return
            ;;
        --format)
            # PCAP output format
            COMPREPLY=($(compgen -W "to_plain_text" -- "$cur"))
            return
            ;;
        --frame|--frame_start|--frame_end|--skip)
            # Frame numbers - user types these
            return
            ;;
        --frame_list)
            # Comma-separated frame numbers - user types these
            return
            ;;
        --tsharkArgsAppend)
            # User types raw tshark arguments
            return
            ;;
        -ic|--interactive-chain)
            # Suggest hw_server interactive commands
            COMPREPLY=($(compgen -W "1 2 3 program scan_ila scan_jtag i1 i2 v1 v2 s1 w1 c1 q" -- "$cur"))
            return
            ;;
    esac

    # Check which tool is selected to provide context-specific completions
    local tool=$(_get_flag_value "--tool")
    local cmd=$(_get_flag_value "--cmd")

    # Provide completions based on the selected tool
    case "$tool" in
        vivado)
            # Primary action flags (show first)
            local vivado_action_flags="--syn --impl --bit --all --lint --list_runs --reset_run --generate_prj_with_external_tcl --write_tcl --file_add --file_remove --clean_logs"
            
            # Check which action is selected to determine appropriate modifiers
            local selected_action=""
            for flag in $vivado_action_flags; do
                if _word_in_args "$flag"; then
                    selected_action="$flag"
                    break
                fi
            done
            
            if [[ "$cur" == -* || -z "$cur" ]]; then
                local available_flags=""
                
                if [ -n "$selected_action" ]; then
                    # Determine modifiers based on selected action
                    local modifier_flags=""
                    case "$selected_action" in
                        --syn|--impl|--bit|--all|--lint|--reset_run)
                            # Build steps: only --clean
                            modifier_flags="--clean"
                            ;;
                        --generate_prj_with_external_tcl)
                            # Generate project: --clean --force
                            modifier_flags="--clean --force"
                            ;;
                        --file_add|--file_remove)
                            # File operations: --file_path required
                            modifier_flags="--file_path"
                            ;;
                        --list_runs|--write_tcl)
                            # List/export: no modifiers needed
                            modifier_flags=""
                            ;;
                        --clean_logs)
                            # Clean logs: --force --verbose
                            modifier_flags="--force --verbose"
                            ;;
                    esac
                    
                    # Filter out already used flags
                    for flag in $modifier_flags; do
                        _word_in_args "$flag" || available_flags="$available_flags $flag"
                    done
                else
                    # No action yet - show only action flags (filter out already used)
                    for flag in $vivado_action_flags; do
                        _word_in_args "$flag" || available_flags="$available_flags $flag"
                    done
                fi
                
                COMPREPLY=($(compgen -W "$available_flags" -- "$cur"))
            fi
            ;;
        verilator|Verilator)
            local verilator_flags="--step --SimTargetName --clean --verbose"
            if [[ "$cur" == -* || -z "$cur" ]]; then
                local available_flags=""
                for flag in $verilator_flags; do
                    _word_in_args "$flag" || available_flags="$available_flags $flag"
                done
                COMPREPLY=($(compgen -W "$available_flags" -- "$cur"))
            fi
            ;;
        network)
            # First, check if --cmd is already specified
            if [[ -z "$cmd" ]]; then
                # No command yet, suggest --cmd
                if [[ "$cur" == -* || -z "$cur" ]]; then
                    COMPREPLY=($(compgen -W "--cmd --verbose" -- "$cur"))
                fi
            else
                # Command specified, suggest command-specific parameters
                local cmd_params=""
                case "$cmd" in
                    send_raw)
                        cmd_params="$network_send_raw_params"
                        ;;
                    send_arp)
                        cmd_params="$network_send_arp_params"
                        ;;
                    send_icmp)
                        cmd_params="$network_send_icmp_params"
                        ;;
                    send_udp)
                        cmd_params="$network_send_udp_params"
                        ;;
                esac
                
                if [[ "$cur" == -* || -z "$cur" ]]; then
                    # Filter out already used flags
                    local available_flags=""
                    for flag in $cmd_params; do
                        _word_in_args "$flag" || available_flags="$available_flags $flag"
                    done
                    COMPREPLY=($(compgen -W "$available_flags" -- "$cur"))
                fi
            fi
            ;;
        vcd_analyzer)
            # Check if --vcdfilename is provided
            local has_vcdfile=false
            _word_in_args "--vcdfilename" && has_vcdfile=true
            
            # Check if we're after a flag that needs a value
            if [[ "$prev" == "--get_values_pins" || "$prev" == "--get_values_all" || "$prev" == "--find_signal_names" || "$prev" == "--signalnames" ]]; then
                # User is typing the module path - no completion
                return
            fi
            
            # Check for terminal actions that don't need more flags (except --human)
            if _word_in_args "--get_modules_list"; then
                # --get_modules_list is complete, no more flags needed
                return
            fi
            
            if [[ "$cur" == -* || -z "$cur" ]]; then
                local available_flags=""
                
                if [ "$has_vcdfile" = false ]; then
                    # First, require --vcdfilename
                    available_flags="--vcdfilename"
                elif _word_in_args "--get_values_pins" || _word_in_args "--get_values_all"; then
                    # After --get_values_pins or --get_values_all (with path), can add --human
                    if ! _word_in_args "--human"; then
                        available_flags="--human"
                    fi
                else
                    # Show action flags (after --vcdfilename is set)
                    local action_flags="--get_modules_list --get_values_pins --get_values_all --find_signal_names --signalnames"
                    for flag in $action_flags; do
                        _word_in_args "$flag" || available_flags="$available_flags $flag"
                    done
                fi
                
                COMPREPLY=($(compgen -W "$available_flags" -- "$cur"))
            fi
            ;;
        tsharkWrapper)
            # Check if --pcap is provided
            local has_pcap=false
            _word_in_args "--pcap" && has_pcap=true
            
            if [[ "$cur" == -* || -z "$cur" ]]; then
                local available_flags=""
                
                if [ "$has_pcap" = false ]; then
                    # First, require --pcap
                    available_flags="--pcap"
                else
                    # Show frame selection, format options, and tshark args append
                    local tshark_flags="--format --frame --frame_start --frame_end --frame_list --count --skip --tsharkArgsAppend --verbose"
                    for flag in $tshark_flags; do
                        _word_in_args "$flag" || available_flags="$available_flags $flag"
                    done
                fi
                
                COMPREPLY=($(compgen -W "$available_flags" -- "$cur"))
            fi
            ;;
        hw_server)
            # Check for interactive mode flags first
            if _word_in_args "-i" || _word_in_args "--interactive"; then
                # Interactive mode - show config and server options
                local interactive_flags="--hw-config -c --server_ip --bitstream --probes"
                if [[ "$cur" == -* || -z "$cur" ]]; then
                    local available_flags=""
                    for flag in $interactive_flags; do
                        _word_in_args "$flag" || available_flags="$available_flags $flag"
                    done
                    COMPREPLY=($(compgen -W "$available_flags" -- "$cur"))
                fi
                return
            fi
            
            if _word_in_args "-ic" || _word_in_args "--interactive-chain"; then
                # Interactive chain mode - already handled by -ic case above
                return
            fi
            
            # Check if --cmd is already specified
            if [[ -z "$cmd" ]]; then
                # No command yet, suggest --cmd or interactive modes
                if [[ "$cur" == -* || -z "$cur" ]]; then
                    COMPREPLY=($(compgen -W "--cmd -i --interactive -ic --interactive-chain --hw-config -c --server_ip" -- "$cur"))
                fi
            else
                # Command specified, suggest command-specific parameters
                local hw_server_params=""
                case "$cmd" in
                    program)
                        hw_server_params="--server_ip --bitstream --probes --hw-config -c"
                        ;;
                    scan_ila)
                        hw_server_params="--server_ip --probes --hw-config -c"
                        ;;
                    scan_jtag|read_dna)
                        hw_server_params="--server_ip --hw-config -c"
                        ;;
                esac
                
                if [[ "$cur" == -* || -z "$cur" ]]; then
                    local available_flags=""
                    for flag in $hw_server_params; do
                        _word_in_args "$flag" || available_flags="$available_flags $flag"
                    done
                    COMPREPLY=($(compgen -W "$available_flags" -- "$cur"))
                fi
            fi
            ;;
        projects)
            # --list is the only option, don't suggest if already used
            if ! _word_in_args "--list"; then
                if [[ "$cur" == -* || -z "$cur" ]]; then
                    COMPREPLY=($(compgen -W "--list" -- "$cur"))
                fi
            fi
            ;;
        *)
            # No tool selected yet, suggest --tool only
            if [[ "$cur" == -* || -z "$cur" ]]; then
                COMPREPLY=($(compgen -W "--tool" -- "$cur"))
            fi
            ;;
    esac
}

# Register the completion function for hdlforge
complete -F _hdlforge_completions hdlforge
