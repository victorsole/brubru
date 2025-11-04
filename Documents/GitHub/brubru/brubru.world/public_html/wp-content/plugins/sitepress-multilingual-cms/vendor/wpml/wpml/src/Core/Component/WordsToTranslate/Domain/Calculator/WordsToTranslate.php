<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Calculator;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Ideogram\PrepareContent as PrepareContentIdeogram;
use WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Letter\PrepareContent as PrepareContentLetter;
use WPML\Core\Component\WordsToTranslate\Domain\Config;
use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\LastTranslation;

class WordsToTranslate {

  /** @var Diff */
  private $diff;

  /** @var Count */
  private $count;

  /** @var PrepareContentLetter */
  private $prepareContentLetter;

  /** @var PrepareContentIdeogram */
  private $prepareContentIdeogram;


  public function __construct(
    Diff $diff,
    Count $count,
    PrepareContentLetter $prepareContentLetter,
    PrepareContentIdeogram $prepareContentIdeogram
  ) {
    $this->diff = $diff;
    $this->count = $count;
    $this->prepareContentLetter = $prepareContentLetter;
    $this->prepareContentIdeogram = $prepareContentIdeogram;
  }


  /** @return void */
  public function forLastTranslation( LastTranslation $lastTranslation, Item $original ) {
    $sourceLang = strtolower( $original->getSourceLang() );
    $prepare = $this->prepareContentLetter;
    $countFactor = 1;

    // Some languages use ideograms - these languages have a different calculation.
    if ( isset( Config::LANGS[$sourceLang][Config::KEY_WORDS_PER_IDEOGRAM] ) ) {
      $prepare = $this->prepareContentIdeogram;
      $countFactor = Config::LANGS[$sourceLang][Config::KEY_WORDS_PER_IDEOGRAM];
    }

    $diff = $this->diff->diffArrays(
      $prepare->prepareForDiff( $lastTranslation->getOriginalContent() ?? '' ),
      $prepare->prepareForDiff( $original->getContent() ?? '' )
    );

    $lastTranslation->setDiffWordsToOriginal( $diff );
    $lastTranslation->setWordsToTranslate(
      (int) ( round( $this->count->wordsToTranslate( $diff ) * $countFactor ) )
    );
  }


}
