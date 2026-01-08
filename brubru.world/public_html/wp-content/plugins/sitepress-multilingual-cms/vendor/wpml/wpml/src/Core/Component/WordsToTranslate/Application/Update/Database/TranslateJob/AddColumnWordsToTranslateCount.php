<?php

namespace WPML\Core\Component\WordsToTranslate\Application\Update\Database\TranslateJob;

use WPML\Core\Port\Persistence\DatabaseAlterInterface;
use WPML\Core\Port\Update\UpdateInterface;
use WPML\PHP\Exception\Exception;

class AddColumnWordsToTranslateCount implements UpdateInterface {

  /** @var DatabaseAlterInterface */
  private $db;


  public function __construct( DatabaseAlterInterface $db ) {
    $this->db = $db;
  }


  public function update() {
    try {
      return $this->db->addColumn(
        'icl_translate_job',
        'wpml_words_to_translate_count',
        DatabaseAlterInterface::FIELD_TYPE_INT11_UNSIGNED
      ) && $this->db->addColumn(
        'icl_translate_job',
        'wpml_automatic_translation_costs',
        DatabaseAlterInterface::FIELD_TYPE_INT11_UNSIGNED
      );
    } catch ( Exception $e ) {
      return false;
    }
  }


}
