<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Strings;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\WordsToTranslate;
use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\LastTranslationFactory;
use WPML\Core\Component\WordsToTranslate\Domain\ProviderInterface;
use WPML\Core\Component\WordsToTranslate\Domain\Strings\Query\StringQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\Strings\Query\TranslationQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\TranslatableDTO;
use WPML\PHP\Exception\InvalidItemIdException;

class Provider implements ProviderInterface {
  const TYPE = 'string';

  /** @var StringQueryInterface */
  private $stringQuery;

  /** @var TranslationQueryInterface */
  private $translationQuery;

  /** @var LastTranslationFactory */
  private $lastTranslationFactory;

  /** @var WordsToTranslate */
  private $wordsToTranslate;


  public function __construct(
    StringQueryInterface $stringQuery,
    TranslationQueryInterface $translationQuery,
    LastTranslationFactory $lastTranslationFactory,
    WordsToTranslate $wordsToTranslate
  ) {
    $this->stringQuery = $stringQuery;
    $this->translationQuery = $translationQuery;
    $this->lastTranslationFactory = $lastTranslationFactory;
    $this->wordsToTranslate = $wordsToTranslate;
  }


  /**
   * @param int $id
   * @param string $type
   * @param string[] $langs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Item|false
   *
   * @throws InvalidItemIdException
   */
  public function getByIdAndTypeForLangs( $id, $type, $langs, $freshTranslation = false ) {
    if ( $type !== self::TYPE ) {
      return false;
    }

    $string = $this->stringQuery->getById( $id );

    foreach ( $langs as $lang ) {
      $lastTranslation = $this->lastTranslationFactory->createForItem( $string, $lang );

      if ( $lang === $string->getSourceLang() ) {
        // TM Dashboard shows also strings which are not in the seleected source
        // language, so it can happen that the requested language is the same as
        // the source language. In that case there is simply nothing to translate.
        $lastTranslation->setOriginalContent( $string->getContent() ?: '' );
        $lastTranslation->setWordsToTranslate( 0 );
        $string->addLastTranslation( $lastTranslation );
        continue;
      }

      $lastTranslationContent = $freshTranslation
        ? ''
        : $this->translationQuery->getLastTranslatedOriginalContent( $string, $lang );
      $lastTranslation->setOriginalContent( $lastTranslationContent );

      $this->wordsToTranslate->forLastTranslation( $lastTranslation, $string );
      $string->addLastTranslation( $lastTranslation );
    }

    return $string;
  }


  /**
   * @param int $id
   * @param string $type
   * @param TranslatableDTO[] $content
   *
   * @return void
   */
  public function useThisContentForItem( $id, $type, $content ) {
    // Nothing to do here for strings.
  }


}
