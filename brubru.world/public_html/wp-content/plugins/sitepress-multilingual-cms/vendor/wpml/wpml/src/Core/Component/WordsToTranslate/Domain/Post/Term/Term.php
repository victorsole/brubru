<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post\Term;

class Term {

  /** @var int */
  private $id;

  /** @var TermContent[] I.e. title, description, meta-field-foo... */
  private $contents = [];


  public function __construct(
    int $id
  ) {
    $this->id = $id;
  }


  /** @return int */
  public function getId() {
    return $this->id;
  }


  /** @return void */
  public function addContent( TermContent $content ) {
    $this->contents[] = $content;
  }


  /** @return TermContent[] */
  public function getContents() {
    return $this->contents;
  }


}
