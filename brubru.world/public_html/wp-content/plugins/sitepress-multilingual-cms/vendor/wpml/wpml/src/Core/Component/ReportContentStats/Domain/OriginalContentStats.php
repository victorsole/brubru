<?php

namespace WPML\Core\Component\ReportContentStats\Domain;

class OriginalContentStats {

  /** @var string */
  private $postType;

  /** @var int */
  private $postsCount;

  /** @var int */
  private $charactersCount;


  public function __construct( string $postType, int $postsCount, int $charactersCount ) {
    $this->postType        = $postType;
    $this->postsCount      = $postsCount;
    $this->charactersCount = $charactersCount;
  }


  public function getPostType(): string {
    return $this->postType;
  }


  public function getPostsCount(): int {
    return $this->postsCount;
  }


  public function getCharactersCount(): int {
    return $this->charactersCount;
  }


}
