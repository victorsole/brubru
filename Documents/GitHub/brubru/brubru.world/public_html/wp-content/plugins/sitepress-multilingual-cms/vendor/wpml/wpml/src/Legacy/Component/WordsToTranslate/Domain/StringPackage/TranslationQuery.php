<?php

// phpcs:ignoreFile Squiz.NamingConventions.ValidVariableName.MemberNotCamelCaps
namespace WPML\Legacy\Component\WordsToTranslate\Domain\StringPackage;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query\TranslationQueryInterface;

// Legacy
use WPML\Translation\TranslationElements\FieldCompression;

class TranslationQuery implements TranslationQueryInterface {


  public function getLastTranslatedOriginalContent( Item $stringPackage, string $lang ) {
    $sitepress = $GLOBALS['sitepress'];

    $package = new \WPML_Package( $stringPackage->getId() );

    $trid = $sitepress->get_element_trid(
      $package->ID,
      $package->get_translation_element_type()
    );

    if ( ! $trid ) {
        return '';
    }

    $wpdb = $GLOBALS['wpdb'];

    // Get the last completed job ID
    $jobId = $wpdb->get_var(
      $wpdb->prepare(
        "SELECT j.job_id
         FROM {$wpdb->prefix}icl_translate_job j
         JOIN {$wpdb->prefix}icl_translation_status s ON j.rid = s.rid
         JOIN {$wpdb->prefix}icl_translations t ON s.translation_id = t.translation_id
         WHERE t.trid = %d
         AND j.completed_date IS NOT NULL
         AND j.editor = 'ate'
         AND t.language_code = %s
         ORDER BY j.completed_date DESC
         LIMIT 1;",
         $trid,
         $lang
      )
    );

    if ( $jobId === null ) {
      // No completed job found for this post.
      return '';
    }

    $elements = $wpdb->get_results(
      $wpdb->prepare(
        "SELECT translate.*
			  FROM {$wpdb->prefix}icl_translate translate
			  WHERE job_id = %d",
        $jobId
      )
    );

    if ( ! $elements ) {
      // No elements found for this job. Probably an older job as only the
      // elements of the latest completed job are stored. How can the job not be
      // the lastest compelted? When the user switched to CTE.
      return '';
    }

    $lastTranslatedContent = '';

    foreach ( $elements as $element ) {
      if ( ! $element->field_translate ) {
        continue;
      }

      // Exclude all term related fields (handled separately).
      if (
        strpos( $element->field_type, 't_' ) === 0
        || strpos( $element->field_type, 'tdesc_' ) === 0
        || strpos( $element->field_type, 'tfield' ) === 0
      ) {
        continue;
      }

      $content = trim(
        FieldCompression::decompress( $element->field_data ) ?? ''
      );

      $lastTranslatedContent .= $content ? ' ' . $content : '';
    }

    return trim( $lastTranslatedContent );
  }


}
