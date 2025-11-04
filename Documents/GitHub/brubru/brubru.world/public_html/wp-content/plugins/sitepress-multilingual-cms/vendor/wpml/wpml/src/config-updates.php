<?php

/**
 *  Updates
 *   - id                         Unique numeric ID of the update.
 *                                Once set, it cannot be changed as it is
 *                                used to identify if the update already ran.
 *   - handler                    Class to execute. Must implement UpdateInterface.
 *   - tryOnlyOnce (optional)     Default: false.
 *                                If true, the update will run only once no
 *                                matter if it works or not.
 *   - lazyLoad (optional)        Default: false.
 *                                If true, the update will run after the page
 *                                was loaded - triggered by script.
 */

use WPML\Core\Component\Translation\Application\Update\Database\Links\AddTablesForLinksTranslation;
use WPML\Core\Component\Translation\Application\Update\Database\TranslationStatus\AddIndexForReviewStatus;
use WPML\Core\Component\WordsToTranslate\Application\Update\Database\TranslateJob\AddColumnWordsToTranslateCount;

return [
  [
    'id' => 1,
    'handler'     => AddIndexForReviewStatus::class,
    'tryOnlyOnce' => true,
    'lazyLoad'   => true,
  ],
  [
    'id' => 2,
    'handler' => AddColumnWordsToTranslateCount::class,
  ],
  [
    'id' => 3,
    'handler' => AddTablesForLinksTranslation::class,
  ],
];
