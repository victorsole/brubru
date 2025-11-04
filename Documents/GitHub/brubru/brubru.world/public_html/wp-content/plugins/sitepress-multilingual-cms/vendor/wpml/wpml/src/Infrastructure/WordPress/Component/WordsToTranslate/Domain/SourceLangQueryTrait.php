<?php
// phpcs:ignoreFile Squiz.NamingConventions.ValidVariableName.MemberNotCamelCaps
namespace WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain;

use WPML\PHP\Exception\InvalidItemIdException;

trait SourceLangQueryTrait {


  /**
   * @throws InvalidItemIdException
   */
  public function getSourceLang( int $id, string $type ): string {
    $wpdb = $GLOBALS['wpdb'];

    $langs = $wpdb->get_row(
      $wpdb->prepare(
        "SELECT source_language_code, language_code
        FROM {$wpdb->prefix}icl_translations
        WHERE element_type = %s
        AND element_id = %d",
        $type,
        $id
      )
    );

    if ( $langs === null || $langs->language_code === null ) {
      throw new InvalidItemIdException(
        sprintf(
          'No translations found for element type %s and ID %d',
          $type,
          $id
        )
      );
    }

    return $langs->source_language_code
      ?: $langs->language_code; // Source is original language.
  }


}
