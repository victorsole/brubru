<?php

namespace WPML\Core\Component\WordsToTranslate\Domain;

class Item {

  /** @var int */
  protected $id;

  /** @var string */
  protected $type;

  /** @var string */
  protected $sourceLang;

  /** @var ?string */
  protected $content;

  /** @var LastTranslation[] */
  protected $lastTranslations = [];


  public function __construct(
    int $id,
    string $type,
    string $sourceLang
  ) {
    $this->id = $id;
    $this->type = $type;
    $this->sourceLang = $sourceLang;
  }


  /** @return int */
  public function getId() {
    return $this->id;
  }


  /** @return string */
  public function getType() {
    return $this->type;
  }


  /** @return string */
  public function getSourceLang() {
    return $this->sourceLang;
  }


  /** @return void */
  public function setContent( string $content ) {
    $this->content = $content;
  }


  /** @return ?string */
  public function getContent() {
    return $this->content;
  }


  /** @return void */
  public function addLastTranslation( LastTranslation $lastTranslation ) {
     $this->lastTranslations[ $lastTranslation->getLangCode() ] = $lastTranslation;
  }


  /** @return LastTranslation[] */
  public function getLastTranslations() {
    return $this->lastTranslations;
  }


  /**
   * @param ?string $langCode
   *
   * @return int
   */
  public function getWordsToTranslate( $langCode = null ) {
    if ( $langCode !== null ) {
      if ( ! isset( $this->lastTranslations[ $langCode ] ) ) {
        return 0;
      }

      return $this->lastTranslations[ $langCode ]->getWordsToTranslate() ?? 0;
    }

    // All languages.
    $wordsToTranslate = 0;

    foreach ( $this->lastTranslations as $lastTranslation ) {
      $wordsToTranslate += $lastTranslation->getWordsToTranslate() ?? 0;
    }

    return $wordsToTranslate;
  }


}
