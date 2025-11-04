<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post;

class JobDto {

  /** @var string */
  private $content;

  /** @var string[] */
  private $fields;


  /**
   * @param string $content
   * @param string[] $fields
   */
  public function __construct( $content, $fields ) {
    $this->content = $content;
    $this->fields = $fields;
  }


  public function getContent(): string {
    return $this->content;
  }


  /** @return string[] */
  public function getTranslatableFields() {
    return $this->fields;
  }


}
