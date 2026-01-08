<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Job;

class JobDTO {

  /** @var int */
  private $id;

  /** @var int */
  private $wordsToTransalte;

  /** @var int|false */
  private $automaticTranslationCosts;

  /** @var int[] */
  private $previousAteJobIds;


  /**
   * JobDTO constructor.
   *
   * @param int $id
   * @param int $wordsToTranslate
   * @param int|false $automaticTranslationCosts
   * @param int[] $previousAteJobId
   */
  public function __construct(
    $id,
    $wordsToTranslate,
    $automaticTranslationCosts,
    $previousAteJobId = []
  ) {
    $this->id = $id;
    $this->wordsToTransalte = $wordsToTranslate;
    $this->automaticTranslationCosts = $automaticTranslationCosts;
    $this->previousAteJobIds = $previousAteJobId;
  }


  public function getId(): int {
    return $this->id;
  }


  public function getWordsToTranslate(): int {
    return $this->wordsToTransalte;
  }


  /** @return int|false */
  public function getAutomaticTranslationCosts() {
    return $this->automaticTranslationCosts;
  }


  /** @return int[] */
  public function getPreviousAteJobIds() {
    return $this->previousAteJobIds;
  }


}
