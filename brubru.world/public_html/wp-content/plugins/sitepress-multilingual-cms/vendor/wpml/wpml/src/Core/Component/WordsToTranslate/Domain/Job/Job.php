<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Job;

use WPML\Core\Component\WordsToTranslate\Domain\Item;

class Job extends Item {

  /** @var string */
  private $targetLang;

  /** @var Item */
  private $item;

  /** @var bool */
  private $isAutomatic;

  /** @var int[] */
  private $atePreviousJobIds;

  /** @var int|false */
  private $translationEngineCostsPerWord;


  /**
   * @param int $id
   * @param string $sourceLang
   * @param string $targetLang
   * @param Item $item
   * @param bool $isAutomatic
   * @param int[] $atePreviousJobIds
   * @param int|false $translationEngineCostsPerWord
   */
  public function __construct(
    $id,
    $sourceLang,
    $targetLang,
    $item,
    $isAutomatic,
    $atePreviousJobIds,
    $translationEngineCostsPerWord
  ) {
    $this->id = $id;
    $this->type = 'job';
    $this->sourceLang = $sourceLang;
    $this->targetLang = $targetLang;
    $this->item = $item;
    $this->isAutomatic = $isAutomatic;
    $this->atePreviousJobIds = $atePreviousJobIds;
    $this->translationEngineCostsPerWord = $translationEngineCostsPerWord;
  }


  /** @return string */
  public function getTargetLang() {
    return $this->targetLang;
  }


  /** @return Item */
  public function getItem() {
    return $this->item;
  }


  /** @return int */
  public function getId() {
    return $this->id;
  }


  /** @return bool */
  public function isAutomatic() {
    return $this->isAutomatic;
  }


  /** @return int[] */
  public function getPreviousAteJobIds() {
    return $this->atePreviousJobIds;
  }


  /**
  * @param string|null $langCode Not relevant for jobs.
  *
  * @return int
  */
  public function getWordsToTranslate( $langCode = null ) {
    return $this->item->getWordsToTranslate();
  }


  /** @return int|false */
  public function getAutomaticTranslationCosts() {
    if ( $this->translationEngineCostsPerWord === false ) {
      return false;
    }
    return $this->item->getWordsToTranslate() * $this->translationEngineCostsPerWord;
  }


}
