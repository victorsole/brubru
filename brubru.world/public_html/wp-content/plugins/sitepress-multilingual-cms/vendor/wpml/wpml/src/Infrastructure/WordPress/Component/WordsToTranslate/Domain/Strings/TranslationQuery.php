<?php

namespace WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\Strings;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\Strings\Query\TranslationQueryInterface;


class TranslationQuery implements TranslationQueryInterface {


  public function getLastTranslatedOriginalContent( Item $string, string $lang ) {
    $wpdb = $GLOBALS['wpdb'];

    $translatedContent = $wpdb->get_var(
      $wpdb->prepare(
        "SELECT value
        FROM {$wpdb->prefix}icl_string_translations
        WHERE string_id = %d AND language = %s",
        $string->getId(),
        $lang
      )
    );

    if ( $translatedContent ) {
      // Translation exists - a string is only translated once - so the last
      // translated original content is the current content.
      return $string->getContent() ?? '';
    }

    // Not translated yet.
    return '';
  }


}
