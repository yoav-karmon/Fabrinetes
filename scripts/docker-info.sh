#!/bin/bash

# Docker Hub Cloud Repository Images
echo "Fetching all images from ykarmon/fabrinetes repository..."
echo ""

# Get repository info
curl -s "https://hub.docker.com/v2/repositories/ykarmon/fabrinetes/" | jq -r '"Repository: " + .name + " (" + .description + ")"' 2>/dev/null || echo "Repository: ykarmon/fabrinetes"

echo ""
echo "Available tags:"

# Get all tags with details
curl -s "https://hub.docker.com/v2/repositories/ykarmon/fabrinetes/tags/?page_size=100" | jq -r '.results[] | "  ykarmon/fabrinetes:\(.name) - Raw Size: \(.full_size)B (\(.full_size | . / 1024 / 1024 | floor)MB) - Updated: \(.last_updated)"' 2>/dev/null || echo "  No tags found or jq not installed"