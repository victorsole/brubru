<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent;

abstract class PrepareContentAbstract {

  /** @var RulesInterface */
  protected $rules;

  /** @var SplitterInterface */
  protected $splitter;


  /** @return string[] */
  public function prepareForDiff( string $content ) {
    $content = $this->rules->applyRules( $content );
    return $this->splitter->stringToArray( $content );
  }


}
