<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules;

interface ShortcodeInterface {


  public function removeShortcodes( string $content ): string;


}
