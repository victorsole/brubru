<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Ideogram;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\PrepareContentAbstract;

class PrepareContent extends PrepareContentAbstract {


  public function __construct(
    Rules $rules,
    Splitter $spliter
  ) {
    $this->rules = $rules;
    $this->splitter = $spliter;
  }


}
