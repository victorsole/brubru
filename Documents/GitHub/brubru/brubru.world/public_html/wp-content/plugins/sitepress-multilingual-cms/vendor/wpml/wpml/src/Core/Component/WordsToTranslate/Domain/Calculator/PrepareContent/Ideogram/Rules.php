<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Ideogram;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules\HTMLTrait;
use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules\NinjaFormFieldsTrait;
use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules\NumbersTrait;
use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules\PunctuationAndSpaceTrait;
use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules\ShortcodeInterface;
use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules\UnicodeTrait;
use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\RulesInterface;

class Rules implements RulesInterface {
  use HTMLTrait;
  use NumbersTrait;
  use PunctuationAndSpaceTrait;
  use NinjaFormFieldsTrait;
  use UnicodeTrait;

  /** @var ShortcodeInterface $shortcode */
  private $shortcode;


  public function __construct( ShortcodeInterface $shortcode ) {
    $this->shortcode = $shortcode;
  }


  /** @return string */
  public function applyRules( string $content ) {
    // Remove HTML tags, but keep translatable attribute's content.
    $content = $this->removeHTMLExceptTranslatableAttributes( $content );

    // Remove ninja form fields.
    $content = $this->removeNinjaFormFields( $content );

    // Remove shortcodes.
    $content = $this->shortcode->removeShortcodes( $content );

    // No charge for puncation changes.
    $content = $this->removePunctuationAndSpaces( $content );

    // Remove standalone numbers.
    $content = $this->removeStandaloneNumbers( $content );

    // Replace unicode characters.
    $content = $this->replaceUnicode( $content );

    return $content;
  }


}
