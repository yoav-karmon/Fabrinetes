#!/usr/bin/env python3

import sys
from helper_functions.config.name_generator import CommandConfig

def test(args, container_info):
    """Run all commands in test mode - automatically discovers and tests all available commands"""
    
    help_flag = getattr(args, 'help', False)
    
    if help_flag:
        print("Usage: ./fabrinetes --cmd test --config-file <config.toml>")
        print("Run all commands in test mode")
        print("")
        print("This command automatically discovers and runs all available commands")
        print("without requiring sub-flags. It will test:")
        print("")
        
        # Get testable commands dynamically
        testable_commands = CommandConfig.get_testable_commands()
        for cmd_name in testable_commands:
            desc = CommandConfig.get_command_description(cmd_name)
            print(f"  - {cmd_name}: {desc}")
        
        print("")
        print("Note: Commands are run in test mode and will only generate commands,")
        print("not execute them.")
        return
    
    print("🧪 Running all commands in test mode...")
    print("=" * 60)
    
    # Get all testable commands dynamically
    testable_commands = CommandConfig.get_testable_commands()
    all_commands = CommandConfig.get_all_commands()
    
    success_count = 0
    error_count = 0
    
    for cmd_name in testable_commands:
        print(f"\n📋 Testing command: {cmd_name}")
        print("-" * 40)
        
        try:
            # Get command definition
            cmd_def = all_commands[cmd_name]
            
            # Create a test args object with minimal required attributes
            class TestArgs:
                def __init__(self):
                    # Add all possible attributes that commands might check
                    self.help = False
                    self.show_help = False  # Add missing show_help attribute
                    self.tarball = False
                    self.rm = False
                    self.x11 = False
                    self.no_x11 = False
                    self.usb = False
                    self.ask = False
                    self.verbose = False
                    self.image = False
                    self.tag = None
                    self.message = None
            
            test_args = TestArgs()
            
            # Call the command function
            cmd_def.function(test_args, container_info)
            
            print(f"✅ {cmd_name}: Success")
            success_count += 1
            
        except Exception as e:
            print(f"❌ {cmd_name}: Error - {e}")
            error_count += 1
    
    print("\n" + "=" * 60)
    print(f"🎯 Test Results:")
    print(f"   ✅ Successful: {success_count}")
    print(f"   ❌ Failed: {error_count}")
    print(f"   📊 Total: {success_count + error_count}")
    
    if error_count > 0:
        print(f"\n⚠️  {error_count} command(s) failed. Check the output above for details.")
        sys.exit(1)
    else:
        print(f"\n🎉 All commands passed successfully!")