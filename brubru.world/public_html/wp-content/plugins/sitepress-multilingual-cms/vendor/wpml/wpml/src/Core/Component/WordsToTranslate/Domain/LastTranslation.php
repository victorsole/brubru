<?php

namespace WPML\Core\Component\WordsToTranslate\Domain;

class LastTranslation {

  /** @var string */
  private $langCode;

  /** @var ?string The source language content and not the translated content. */
  private $originalContent;

  /** @var ?int */
  private $wordsToTranslate;

  /** @var ?array<int, string|array<string,string[]>> */
  private $diffWordsToOriginal;


  public function __construct(
    string $langCode
  ) {
    $this->langCode = $langCode;
  }


  /** @return string */
  public function getLangCode() {
    return $this->langCode;
  }


  /** @return void */
  public function setOriginalContent( string $content ) {
    $this->originalContent = $content;
  }


  /** @return ?string */
  public function getOriginalContent() {
    return $this->originalContent;
  }


  /**
   * @param int $wordsToTranslate
   *
   * @return void
   */
  public function setWordsToTranslate( $wordsToTranslate ) {
    $this->wordsToTranslate = $wordsToTranslate;
  }


  /** @return ?int */
  public function getWordsToTranslate() {
    return $this->wordsToTranslate;
  }


  /**
   * @param array<int, string|array<string,string[]>> $diff
   *
   * @return void
   */
  public function setDiffWordsToOriginal( $diff ) {
    $this->diffWordsToOriginal = $diff;
  }


  /** @return ?array<int, string|array<string,string[]>> */
  public function getDiffWordsToOriginal() {
    return $this->diffWordsToOriginal;
  }


}
