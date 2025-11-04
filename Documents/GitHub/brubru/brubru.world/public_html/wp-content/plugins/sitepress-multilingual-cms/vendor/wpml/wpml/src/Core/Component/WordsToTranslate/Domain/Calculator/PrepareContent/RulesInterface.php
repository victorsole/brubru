<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent;

interface RulesInterface {


  /** @return string */
  public function applyRules( string $content );


}
