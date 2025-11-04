#!/bin/bash

# Run phpdoc-md command from the project root
cd "$(dirname "$0")/.." || exit
vendor/bin/phpdoc-md

# Run merge-docs.php script
php scripts/merge-docs.php