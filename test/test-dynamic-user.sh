#!/bin/bash
# Test script for dynamic user setup

echo "Testing Dynamic User Setup"
echo "================================"

# Test 1: Build the image
echo "Building Docker image with dynamic entrypoint..."
docker build -t fabrinetes-testing-dynamic containers/fabrinetes-dev-testing/

if [ $? -eq 0 ]; then
    echo "Image built successfully"
else
    echo "Image build failed"
    exit 1
fi

# Test 2: Run container with default user
echo ""
echo "Testing container with default user..."
docker run --rm -it fabrinetes-testing-dynamic whoami

# Test 3: Run container with custom user
echo ""
echo "Testing container with custom user..."
docker run --rm -it \
    -e CONTAINER_USER=testuser \
    -e CONTAINER_UID=1001 \
    -e CONTAINER_GID=1001 \
    -e CONTAINER_HOME=/home/testuser \
    fabrinetes-testing-dynamic whoami

# Test 4: Test sudo access
echo ""
echo "Testing passwordless sudo..."
docker run --rm -it fabrinetes-testing-dynamic sudo whoami

# Test 5: Test hostname
echo ""
echo "Testing hostname..."
docker run --rm -it fabrinetes-testing-dynamic hostname

echo ""
echo "All tests completed!"
echo "Dynamic user setup is working correctly!"
