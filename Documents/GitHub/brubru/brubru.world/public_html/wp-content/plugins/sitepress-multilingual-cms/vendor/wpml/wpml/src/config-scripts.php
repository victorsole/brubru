<?php

/**
 * ONLY USE THIS FOR GENERAL SCRIPTS.
 * For page-specific scripts, add the script to the page config.
 *
 *  Scripts
 *   - [arrayKey]                  Id of the script.
 *      - src                      Script source path. Start with 'public/js/...'.
 *      - usedOn (optional)        Default: 'admin'
 *                                 'admin' | 'front' | 'both'
 *                                 ('front' | 'both' are not implemented yet - as not needed).
 *      - onlyRegister (optional)  Default: false.
 *                                 If true, the script will only be registered.
 *                                 (And is only loaded if it is a dependency of another script).
 *      - dependencies (optional)  Array of script dependencies.
 *      - prerequisites (optional) Classname of script prerequisites
 *                                 (must implement ScriptPrerequisitesInterface).
 *      - dataProvider (optional)  Classname of data provider
 *      - inFooter (optional)      Default: true
 *                                 If false, the script will be loaded in the header.
 *
 */

use WPML\UserInterface\Web\Core\Component\PostHog\Application\PostHogController;

return [
  'wpml-node-modules' => [
    'src'          => 'public/js/node-modules.js',
    'onlyRegister' => true,
  ],
  'wpml-posthog-capture-event' => [
    'src' => 'public/js/wpml-posthog-capture-event.js',
    'onlyRegister' => true,
  ],
  'wpml-posthog'      => [
    'src'           => 'public/js/wpml-posthog.js',
    'dependencies'  => [ 'wpml-node-modules', 'wpml-posthog-capture-event' ],
    'prerequisites' => PostHogController::class,
    'dataProvider'  => PostHogController::class,
  ],
];
