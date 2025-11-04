<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\StringBatch;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\ProviderInterface;
use WPML\Core\Component\WordsToTranslate\Domain\StringBatch\Query\StringBatchQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\Strings\Provider as StringProvider;
use WPML\Core\Component\WordsToTranslate\Domain\TranslatableDTO;
use WPML\PHP\Exception\InvalidItemIdException;

class Provider implements ProviderInterface {
  const TYPE = 'stringBatch';

  /** @var StringBatchQueryInterface */
  private $stringBatchQuery;

  /** @var StringProvider */
  private $stringProvider;


  public function __construct(
    StringBatchQueryInterface $stringBatchQuery,
    StringProvider $stringProvider
  ) {
    $this->stringBatchQuery = $stringBatchQuery;
    $this->stringProvider = $stringProvider;
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

    $strings = [];
    $sourceLang = '';

    foreach ( $this->stringBatchQuery->getStringsIdsById( $id ) as $stringId ) {
      $string = $this->stringProvider->getByIdAndTypeForLangs(
        $stringId,
        StringProvider::TYPE,
        $langs,
        $freshTranslation
      );

      if ( ! $string ) {
        continue;
      }

      $sourceLang = $string->getSourceLang();
      $strings[] = $string;
    }

    return new StringBatch(
      $id,
      $sourceLang,
      $strings
    );
  }


  /**
   * @param int $id
   * @param string $type
   * @param TranslatableDTO[] $content
   *
   * @return void
   */
  public function useThisContentForItem( $id, $type, $content ) {
    // Nothing to do here for string batches.
  }


}
