<?php

namespace WPML\Core\Component\WordsToTranslate\Domain;

class TranslatableDTO {

  /** @var string $type */
  private $type;

  /** @var string $content */
  private $content;

  /** @var string $format */
  private $format;


  public function __construct( string $type, string $content, string $format ) {
    $this->type = $type;
    $this->content = $content;
    $this->format = $format;
  }


  public function getType(): string {
    return $this->type;
  }


  public function getContent(): string {
    return $this->content;
  }


  public function getFormat(): string {
    return $this->format;
  }


}
