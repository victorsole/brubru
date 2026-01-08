<?php

namespace WPML\Core\Component\ReportContentStats\Domain;

class PostTypeStats {

  /** @var string */
  private $postTypeId;

  /** @var int */
  private $postsCount;

  /** @var int */
  private $charactersCount;

  /** @var array<string, float> */
  private $translationCoverage;


  /**
   * @param int $postsCount
   * @param int $charactersCount
   * @param array<string, float> $translationCoverage
   */
  public function __construct(
    string $postTypeId,
    int $postsCount,
    int $charactersCount,
    array $translationCoverage
  ) {
    $this->postTypeId          = $postTypeId;
    $this->postsCount          = $postsCount;
    $this->charactersCount     = $charactersCount;
    $this->translationCoverage = $translationCoverage;
  }


  public function getPostTypeId(): string {
    return $this->postTypeId;
  }


  public function getPostsCount(): int {
    return $this->postsCount;
  }


  public function getCharactersCount(): int {
    return $this->charactersCount;
  }


  /**
   * @return array<string, float>
   */
  public function getTranslationCoverage(): array {
    return $this->translationCoverage;
  }


}
