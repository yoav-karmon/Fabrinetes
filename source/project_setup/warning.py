import argparse
import pickle
import os
from tabulate import tabulate

DEFAULT_MAX_LENGTH = 100  # Default max message length
TABLE_STYLE = "grid"  # Default table format

def truncate_text(text, length):
    return text if len(text) <= length else text[:length] + "..."

def parse_log_file(log_file, max_length):
    log_dict = {}

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Step 1: Split by ":"
            type_split = line.split(":", 1)
            if len(type_split) != 2:
                # If no ":", store as MSG type
                msg_type, code, subcode, message = "MSG", "UNKNOWN", "UNKNOWN", truncate_text(line, max_length)
            else:
                msg_type, rest = type_split[0].strip(), type_split[1].strip()

                # If no "[", treat entire line as MSG
                if  not rest.startswith("["):
                    msg_type=msg_type.split(' ')[0]
                    if len(msg_type)<3: 
                       msg_type, code, subcode, message = "MSG", "UNKNOWN", "UNKNOWN", truncate_text(line, max_length)
                    else:
                       code, subcode, message = "UNKNOWN", "UNKNOWN", truncate_text(line, max_length)
                       msg_type="*"+msg_type
                else:
                    # Step 2: Extract code and subcode
                    code_split = rest.split("[", 1)
                    if len(code_split) != 2:
                        continue  # Invalid format, skip

                    before_code, code_part = code_split[0].strip(), code_split[1]

                    # Step 3: Extract code & message
                    code_parts = code_part.split("]", 1)
                    if len(code_parts) != 2:
                        continue  # Invalid format, skip

                    code_subcode, message = code_parts[0].strip(), code_parts[1].strip()

                    # Step 4: Extract Code and Subcode
                    code_sub_split = code_subcode.split(" ", 1)
                    if len(code_sub_split) == 2:
                        code, subcode = code_sub_split
                    else:
                        code, subcode = code_sub_split[0], "UNKNOWN"  # Default if no subcode

                    message = truncate_text(message, max_length)  # Truncate message

            # Store in dictionary
            if msg_type not in log_dict:
                log_dict[msg_type] = {}

            if code not in log_dict[msg_type]:
                log_dict[msg_type][code] = {}

            if subcode not in log_dict[msg_type][code]:
                log_dict[msg_type][code][subcode] = []

            log_dict[msg_type][code][subcode].append(message)

    return log_dict

def save_to_bin(data, bin_file):
    with open(bin_file, "wb") as f:
        pickle.dump(data, f)

def load_from_bin(bin_file):
    with open(bin_file, "rb") as f:
        return pickle.load(f)

def print_table(data, filter_str, max_length):
    table_data = []
    available_types = list(data.keys())
    available_main_types = [key for key in data.keys() if not key.startswith("*")]
    # Parse filter: "WARNING,DRC,REQP-1935"
    filters = filter_str.split(",") if filter_str else []
    filter_type = filters[0] if len(filters) > 0 else None
    filter_code = filters[1] if len(filters) > 1 else None
    filter_subcode = filters[2] if len(filters) > 2 else None
       
    for msg_type, codes in data.items():
        if filter_type==None:
            if "*"in msg_type :
                  continue
        else:
           if filter_type!="*":
               if(msg_type != filter_type) :
                   continue
        for code, subcodes in codes.items():
            if filter_code and code != filter_code:
                continue
            for subcode, messages in subcodes.items():
                if filter_subcode and subcode != filter_subcode:
                    continue
                for msg in messages:
                    table_data.append([msg_type, code, subcode, truncate_text(msg, max_length)])

    if not table_data:
        print("✅ No matching log messages found.")
        return

    print("\n" + tabulate(table_data, headers=["Type", "Code", "Subcode", "Message"], tablefmt=TABLE_STYLE))

    if not filter_str:
        print("\n🔹 Use `-t Type,Code,Subcode` to filter messages.")
        print(f"📝 Available types: {', '.join(available_main_types)}")
        print(f"📝 Available types: {', '.join(available_types)}")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse log files and save/load data.")
    parser.add_argument("-f", "--file", help="Log text file to parse")
    parser.add_argument("-b", "--bin", help="Binary file to load and print")
    parser.add_argument("-t", "--type", help="Filter logs using `Type,Code,Subcode` (e.g., WARNING,DRC,REQP-1935)")
    parser.add_argument("-l", "--length", type=int, default=DEFAULT_MAX_LENGTH, help="Max message length (default: 100)")

    args = parser.parse_args()

    if args.file:
        log_data = parse_log_file(args.file, args.length)
        bin_file = os.path.splitext(args.file)[0] + ".bin"
        save_to_bin(log_data, bin_file)
        print(f"✅ Log data saved to {bin_file}")

    elif args.bin:
        log_data = load_from_bin(args.bin)
        print_table(log_data, args.type, args.length)

    else:
        print("❌ Error: Provide either -f <logfile> or -b <binfile>")

