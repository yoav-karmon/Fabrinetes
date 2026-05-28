HDLForge VCD analyzer

VCD file:
  _verilator/<test>/dump.vcd

List modules:
  hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_modules_list

Show module pins:
  hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_pins '<module.path>'

Show all module signals:
  hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_all '<module.path>'

Human format:
  hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_pins '<module.path>' --human

Use flow:
  run simulation
  find dump.vcd
  list modules
  inspect pins or all signals for one module
