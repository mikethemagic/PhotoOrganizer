#!/bin/bash

export PROJECT=/mnt/c/10-Develop/gitrepos/PhotoOrganiser
export PROJECT_BIN=$PROJECT/bin
export PROJECT_DATA=$PROJECT/data
export PROJECT_SCRIPTS=$PROJECT/scripts
export PROJECT_CACHE=$PROJECT/cache
export PROJECT_LIB=$PROJECT/lib


# Create directories if they don't exist
mkdir -p "$PROJECT/scripts"
mkdir -p "$PROJECT/data"
mkdir -p "$PROJECT/cache"

# Add project bin to PATH
export PATH="$PROJECT_BIN:$PATH"
