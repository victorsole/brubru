<?php

/**
 * Script to merge all generated markdown documentation files into a single README.md file.
 */

// Define paths
$generatedDir = __DIR__ . '/../docs/generated';
$outputFile = __DIR__ . '/../docs/README.md';
$coreDir = __DIR__ . '/../core';
$phpdocMdFile = __DIR__ . '/../.phpdoc-md';

// Check if generated directory exists
if (!is_dir($generatedDir)) {
    echo "Error: Generated documentation directory not found at {$generatedDir}\n";
    exit(1);
}

// Get all markdown files
$files = glob($generatedDir . '/*.md');
if (empty($files)) {
    echo "Warning: No markdown files found in {$generatedDir}, will attempt to generate from PHP files\n";
    $files = [];
}

// Get the list of classes from .phpdoc-md
$phpdocMdConfig = include($phpdocMdFile);
$configuredClasses = [];
foreach ($phpdocMdConfig->classes as $class) {
    // Extract the class name without namespace
    $className = basename(str_replace('\\', '/', $class));
    $configuredClasses[] = $className;

    // Check if a markdown file exists for this class
    $mdFile = $generatedDir . '/' . $className . '.md';
    if (!file_exists($mdFile) && !in_array($mdFile, $files)) {
        echo "Class {$className} is in .phpdoc-md but no markdown file was generated. Creating one...\n";

        // Find the PHP file for this class
        $phpFile = $coreDir . '/' . $className . '.php';

        // Special case for Str class, which is defined in Strings.php
        if ($className === 'Str' && !file_exists($phpFile)) {
            $phpFile = $coreDir . '/Strings.php';
        }

        if (file_exists($phpFile)) {
            // Create a more detailed markdown file for this class
            $phpContent = file_get_contents($phpFile);

            // Extract class description from PHPDoc
            $classDescription = "";
            if (preg_match('/\/\*\*\s*(.*?)\s*\*\//s', $phpContent, $matches)) {
                $classDescription = $matches[1];
                // Clean up the description
                $classDescription = preg_replace('/\s*\*\s*@.*$/m', '', $classDescription);
                $classDescription = preg_replace('/\s*\*\s*/m', ' ', $classDescription);
                $classDescription = trim($classDescription);
            }

            // Extract methods from PHPDoc annotations
            $methods = [];
            preg_match_all('/@method\s+static\s+(?:callable|mixed|string|array|bool|int|[^\s]+)\s+([a-zA-Z0-9_]+)\s*\((.*?)\)(.*?)(?=\*\s+@method|\*\/)/s', $phpContent, $matches, PREG_SET_ORDER);

            foreach ($matches as $match) {
                $methodName = $match[1];
                $signature = trim($match[2]);
                $description = trim($match[3]);

                // Clean up the description
                $description = preg_replace('/\s*-\s*Curried\s*::\s*/', "\n\nCurried :: ", $description);
                $description = preg_replace('/\*\s+/', '', $description);

                $methods[$methodName] = [
                    'signature' => $signature,
                    'description' => $description
                ];
            }

            // Create markdown content
            $content = "# {$className}\n\n";
            if ($classDescription) {
                $content .= "{$classDescription}\n\n";
            }

            // Add methods
            foreach ($methods as $methodName => $methodInfo) {
                if ($methodName !== 'init' && $methodName !== 'macro' && $methodName !== 'hasMacro') {
                    $content .= "### {$className}::{$methodName}\n\n";
                    $content .= "**Description**\n\n";
                    $content .= "{$methodInfo['description']}\n\n";
                    $content .= "```php\n";
                    $content .= "public static function {$methodName}({$methodInfo['signature']})\n";
                    $content .= "```\n\n";
                }
            }

            file_put_contents($mdFile, $content);
            $files[] = $mdFile;
            echo "Created markdown file for {$className} with " . count($methods) . " methods\n";
        } else {
            echo "Warning: Could not find PHP file for class {$className}\n";
        }
    }
}

// Sort files to ensure consistent order
sort($files);

// Initialize content with title
$content = "# WPML Functional Programming Library\n\n";
$content .= "## Table of Contents\n\n";

// Arrays to store TOC entries and file contents
$tocEntries = [];
$fileContents = [];
$methodsByClass = [];

// Function to extract PHPDoc annotations for methods from a file
function extractPhpDocMethods($filePath) {
    $content = file_get_contents($filePath);
    $methods = [];

    // Extract PHPDoc annotations for methods with a simpler pattern that should match all method names
    preg_match_all('/@method\s+static\s+(?:callable|mixed|string|array|bool|int|[^\s]+)\s+([a-zA-Z0-9_]+)\s*\(/s', $content, $matches);

    echo "Extracting methods from " . basename($filePath) . ":\n";
    if (!empty($matches[1])) {
        foreach ($matches[1] as $method) {
            // Skip common methods that are already included
            if (!in_array($method, ['init', 'macro', 'hasMacro'])) {
                $methods[] = $method;
                echo "  - Found method: " . $method . "\n";
            }
        }
    } else {
        echo "  - No methods found\n";
    }

    return $methods;
}

// Process each file to extract TOC entries and content
foreach ($files as $file) {
    $className = basename($file, '.md');
    $fileContent = file_get_contents($file);

    echo "Processing file: " . $file . " (class: " . $className . ")\n";

    // Check if there's a corresponding PHP file in the core directory
    $phpFile = $coreDir . '/' . $className . '.php';

    // Special case for Str class, which is defined in Strings.php
    if ($className === 'Str' && !file_exists($phpFile)) {
        $phpFile = $coreDir . '/Strings.php';
    }

    $phpDocMethods = [];

    if (file_exists($phpFile)) {
        echo "Found corresponding PHP file: " . $phpFile . "\n";
        // Extract methods from PHPDoc annotations
        $phpDocMethods = extractPhpDocMethods($phpFile);
    } else {
        echo "No corresponding PHP file found for " . $className . "\n";
    }

    // Extract method names for TOC from the markdown file
    preg_match_all('/^### ' . $className . '::([a-zA-Z0-9_]+)\s*$/m', $fileContent, $matches);
    $methods = [];

    if (!empty($matches[1])) {
        foreach ($matches[1] as $method) {
            $methods[] = $method;
            $methodsByClass[$className][] = $method;
        }
    }

    // Add PHPDoc methods to the list if they're not already included
    if (!empty($phpDocMethods)) {
        foreach ($phpDocMethods as $method) {
            if (!in_array($method, $methods) && $method !== 'init' && $method !== 'macro' && $method !== 'hasMacro') {
                $methodsByClass[$className][] = $method;
            }
        }
    }

    // Store file content (excluding the first line which is the class title)
    $lines = explode("\n", $fileContent);
    array_shift($lines); // Remove the first line (class title)

    // Clean up the content to match the original format
    $cleanedContent = '';
    $inMethod = false;
    $methodName = '';

    foreach ($lines as $line) {
        // Check if this is a method header
        if (preg_match('/^### ' . $className . '::([a-zA-Z0-9_]+)\s*$/m', $line, $methodMatch)) {
            $methodName = $methodMatch[1];
            $inMethod = true;
            $cleanedContent .= "### {$methodName}\n\n";
            continue;
        }

        // Skip tables and other formatting we don't want
        if (strpos($line, '| Name | Description |') !== false || 
            strpos($line, '|------|-------------|') !== false ||
            strpos($line, '<hr />') !== false) {
            continue;
        }

        // Clean up method descriptions
        if ($inMethod) {
            // Remove "Description" headers
            if (strpos($line, '**Description**') !== false) {
                continue;
            }

            // Remove code blocks for method signatures
            if (strpos($line, '```php') !== false) {
                continue;
            }
            if (strpos($line, 'public') !== false && strpos($line, '(') !== false) {
                continue;
            }
            if (strpos($line, '```') !== false) {
                continue;
            }

            // Keep the actual description
            $cleanedContent .= $line . "\n";
        }
    }

    // Add documentation for PHPDoc methods that are not in the markdown file
    if (!empty($phpDocMethods)) {
        foreach ($phpDocMethods as $method) {
            if (!in_array($method, $methods) && $method !== 'init' && $method !== 'macro' && $method !== 'hasMacro') {
                $cleanedContent .= "### {$method}\n\n";

                // Extract the PHPDoc annotation for this method
                $phpContent = file_get_contents($phpFile);
                if (preg_match('/@method\s+static\s+(?:callable|mixed|[^\s]+)\s+' . $method . '\s*\((.*?)\)(.*?)(?=\*\s+@method|\*\/)/s', $phpContent, $docMatch)) {
                    $signature = trim($docMatch[1]);
                    $description = trim($docMatch[2]);

                    // Clean up the description
                    $description = preg_replace('/\s*-\s*Curried\s*::\s*/', "\n\nCurried :: ", $description);
                    $description = preg_replace('/\*\s+/', '', $description);

                    $cleanedContent .= "**Signature:** `{$method}({$signature})`\n\n";
                    $cleanedContent .= "{$description}\n\n";
                } else {
                    $cleanedContent .= "This method is documented in PHPDoc annotations but not in the generated markdown file.\n\n";
                }
            }
        }
    }

    $fileContents[$className] = $cleanedContent;
}

// Build TOC
foreach ($methodsByClass as $className => $methods) {
    $tocEntries[] = "* [{$className}](#{$className})";
    foreach ($methods as $method) {
        $lowerMethod = strtolower($method);
        $tocEntries[] = "    * [{$method}](#{$lowerMethod})";
    }
}

// Add TOC to content
$content .= implode("\n", $tocEntries) . "\n\n";

// Add file contents
foreach ($fileContents as $className => $fileContent) {
    $content .= "* {$className}\n" . $fileContent . "\n";
}

// Write to output file
if (file_put_contents($outputFile, $content)) {
    echo "Documentation successfully merged into {$outputFile}\n";

    // Clean up: remove the generated directory
    $files = glob($generatedDir . '/*');
    foreach ($files as $file) {
        if (is_file($file)) {
            unlink($file);
        }
    }
    if (rmdir($generatedDir)) {
        echo "Generated directory {$generatedDir} has been removed\n";
    } else {
        echo "Warning: Could not remove generated directory {$generatedDir}\n";
    }
} else {
    echo "Error: Failed to write to {$outputFile}\n";
    exit(1);
}
