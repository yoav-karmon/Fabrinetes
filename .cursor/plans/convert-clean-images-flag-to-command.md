# Convert --clean-images Flag to Clean-Images Command

## Task List: Convert --clean-images Flag to Standalone Clean-Images Command

### 1. Tasks List:
1.1 Remove --clean-images flag from build command parser
1.2 Add clean-images command to command choices
1.3 Create command/clean-images/clean_images.py module
1.4 Implement clean-images command logic for base image (with --base-image)
1.5 Implement clean-images command logic for main image (without --base-image)
1.6 Update build command to remove clean-images functionality
1.7 Update help text and documentation for new command
1.8 Test clean-images command functionality
1.9 Update README and documentation

### 2. Task List Review:
2.1 **Task 1.1**: Remove --clean-images flag from build command parser
   - Files involved: `helper_functions/config/name_generator.py`
   - Update: Remove --clean-images argument from build command section

2.2 **Task 1.2**: Add clean-images command to command choices
   - Files involved: `helper_functions/config/name_generator.py`
   - Update: Add 'clean-images' to command choices list

2.3 **Task 1.3**: Create command/clean-images/clean_images.py module
   - Files involved: `command/clean-images/clean_images.py`, `command/clean-images/__init__.py`
   - Update: Create new command module with clean_images function

2.4 **Task 1.4**: Implement clean-images command logic for base image (with --base-image)
   - Files involved: `command/clean-images/clean_images.py`
   - Update: Add logic to remove base image when --base-image flag is used

2.5 **Task 1.5**: Implement clean-images command logic for main image (without --base-image)
   - Files involved: `command/clean-images/clean_images.py`
   - Update: Add logic to remove main image when --base-image flag is not used

2.6 **Task 1.6**: Update build command to remove clean-images functionality
   - Files involved: `command/build/build.py`
   - Update: Remove clean_images parameter and generate_clean_images_command function

2.7 **Task 1.7**: Update help text and documentation for new command
   - Files involved: `helper_functions/config/name_generator.py`, help text
   - Update: Update help text to include clean-images command

2.8 **Task 1.8**: Test clean-images command functionality
   - Files involved: Test scripts, manual testing
   - Update: Test the clean-images command with both base and main images

2.9 **Task 1.9**: Update README and documentation
   - Files involved: `README.md`, command documentation
   - Update: Update documentation to reflect new clean-images command

### 3. Task List Global Review:
3.1 Update tasks to keep files under ~400 lines by:
   3.1.1 Reuse functions: Extract common clean images logic into helper functions
   3.1.2 Create helper functions: Create helper functions for image cleaning operations
   3.1.3 Cache operations: Cache Docker client and image information for efficiency

### 4. Execute Task List:

#### Task 1.1: Remove --clean-images flag from build command parser ✅
**What I did**: Removed --clean-images argument from build command section in name_generator.py.

#### Task 1.2: Add clean-images command to command choices ✅
**What I did**: Added 'clean-images' to command choices list in name_generator.py.

#### Task 1.3: Create command/clean_images/clean_images.py module ✅
**What I did**: Created new command module with clean_images function and proper structure. Had to rename directory from clean-images to clean_images due to Python import restrictions.

#### Task 1.4: Implement clean-images command logic for base image (with --base-image) ✅
**What I did**: Implemented logic to remove base image when --base-image flag is used. Generates docker rmi command for base image.

#### Task 1.5: Implement clean-images command logic for main image (without --base-image) ✅
**What I did**: Implemented logic to remove main image when --base-image flag is not used. Generates docker rmi command for main image.

#### Task 1.6: Update build command to remove clean-images functionality ✅
**What I did**: Removed clean_images parameter and generate_clean_images_command function from build.py.

#### Task 1.7: Update help text and documentation for new command ✅
**What I did**: Updated help text to include clean-images command with proper examples.

#### Task 1.8: Test clean-images command functionality ✅
**What I did**: Tested the clean-images command functionality:
- ✅ Clean-images with --base-image: Generates docker rmi command for base image
- ✅ Clean-images without --base-image: Generates docker rmi command for main image
- ✅ Build command rejects --clean-images flag: Shows proper error message

#### Task 1.9: Update README and documentation ✅
**What I did**: Updated README and documentation to reflect new clean-images command.

### 5. Implementation Results:
- ✅ **--clean-images flag removed**: No longer a flag on build command
- ✅ **clean-images command added**: New standalone command for image cleaning
- ✅ **Clean images logic implemented**: Works for both base and main images based on --base-image flag
- ✅ **Help text updated**: Reflects new command structure
- ✅ **Functionality tested**: All commands work correctly with new structure
- ✅ **Build command cleaned**: Removed clean-images functionality from build command

### 6. After Completion:
6.1 **README Update**: Updated with new clean-images command
6.2 **Documentation**: Updated command documentation with new command
6.3 **Status**: Clean-images command fully implemented and tested

## Summary:
Successfully converted --clean-images flag to a standalone clean-images command. The system now provides a dedicated command for cleaning Docker images, with the --base-image flag determining whether to clean base or main images. All commands follow the "generate only" pattern while providing comprehensive image management capabilities.
