<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\StringPackage;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\WordsToTranslate;
use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\LastTranslationFactory;
use WPML\Core\Component\WordsToTranslate\Domain\ProviderInterface;
use WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query\JobQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query\StringPackageQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query\TranslationQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\TranslatableDTO;
use WPML\PHP\Exception\InvalidItemIdException;

class Provider implements ProviderInterface {
  const TYPE = 'stringPackage';

  /** @var StringPackageQueryInterface */
  private $stringPackageQuery;

  /** @var JobQueryInterface */
  private $jobQuery;

  /** @var TranslationQueryInterface */
  private $translationQuery;

  /** @var LastTranslationFactory */
  private $lastTranslationFactory;

  /** @var WordsToTranslate */
  private $wordsToTranslate;


  public function __construct(
    StringPackageQueryInterface $stringPackageQuery,
    JobQueryInterface $jobQuery,
    TranslationQueryInterface $translationQuery,
    LastTranslationFactory $lastTranslationFactory,
    WordsToTranslate $wordsToTranslate
  ) {
    $this->stringPackageQuery = $stringPackageQuery;
    $this->jobQuery = $jobQuery;
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

    $stringPackage = $this->stringPackageQuery->getById( $id );

    foreach ( $langs as $lang ) {
      $stringPackage->setContent(
        $this->jobQuery->getContent( $stringPackage, $lang )
      );
      $lastTranslation = $this->lastTranslationFactory->createForItem( $stringPackage, $lang );

      $lastTranslationContent = $freshTranslation
        ? ''
        : $this->translationQuery->getLastTranslatedOriginalContent( $stringPackage, $lang );
      $lastTranslation->setOriginalContent( $lastTranslationContent );

      $this->wordsToTranslate->forLastTranslation( $lastTranslation, $stringPackage );
      $stringPackage->addLastTranslation( $lastTranslation );
    }

    return $stringPackage;
  }


  /**
   * @param int $id
   * @param string $type
   * @param TranslatableDTO[] $content
   *
   * @return void
   */
  public function useThisContentForItem( $id, $type, $content ) {
    if ( $type !== self::TYPE ) {
      return;
    }

    $this->jobQuery->useThisContentForItem( $id, $content );
  }


}
