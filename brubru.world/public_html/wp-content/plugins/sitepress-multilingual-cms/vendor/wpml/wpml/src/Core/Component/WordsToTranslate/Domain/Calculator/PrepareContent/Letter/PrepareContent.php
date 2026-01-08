<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Letter;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\PrepareContentAbstract;

class PrepareContent extends PrepareContentAbstract {


  public function __construct(
    Rules $rules,
    Splitter $splitter
  ) {
    $this->rules = $rules;
    $this->splitter = $splitter;
  }


}
