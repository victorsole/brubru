<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Term\Term;

class Post extends Item {

  /** @var int */
  private $lastEdit;

  /** @var ?Term[] */
  private $terms;


  public function __construct(
    int $id,
    string $type,
    string $sourceLang,
    int $lastEdit
  ) {
    parent::__construct( $id, $type, $sourceLang );
    $this->lastEdit = $lastEdit;
  }


  /** @return int */
  public function getLastEdit() {
    return $this->lastEdit;
  }


  /**
   * @param Term[] $terms
   *
   * @return void
   */
  public function setTerms( $terms ) {
    $this->terms = $terms;
  }


  /**
   * @return ?Term[]
   */
  public function getTerms() {
    return $this->terms;
  }


  /**
   * @param ?string $langCode
   *
   * @return int
   */
  public function getWordsToTranslate( $langCode = null ) {
    $wordsToTranslate = 0;

    // Post Content.
    if ( ! $langCode ) {
      // All languages.
      foreach ( $this->lastTranslations as $lastTranslation ) {
        $wordsToTranslate += $lastTranslation->getWordsToTranslate() ?? 0;
      }
    } elseif ( isset( $this->lastTranslations[ $langCode ] ) ) {
      // Specific language.
      $wordsToTranslate = $this->lastTranslations[ $langCode ]->getWordsToTranslate() ?? 0;
    }

    // Terms.
    if ( ! $this->terms ) {
      return $wordsToTranslate;
    }

    foreach ( $this->terms as $term ) {
      foreach ( $term->getContents() as $content ) {
        $wordsToTranslate += $content->getWordsToTranslate( $langCode );
      }
    }

    return $wordsToTranslate;
  }


}
