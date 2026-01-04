#!/bin/bash
# Script to zip the module
cd dolibarr_module
zip -r ../raffles_module.zip raffles
cd ..
echo "Module zipped to raffles_module.zip"
