#!/bin/bash

export PROJECT=/mnt/c/10-Develop/gitrepos/PhotoOrganiser
export PROJECT_BIN=$PROJECT/bin
export PROJECT_DATA=$PROJECT/data
export PROJECT_WORK=$PROJECT/work
export PROJECT_LIB=$PROJECT/lib


# Create directories if they don't exist
mkdir -p "$PROJECT/work"
mkdir -p "$PROJECT/data"

# Add project bin to PATH
export PATH="$PROJECT_BIN:$PATH"
