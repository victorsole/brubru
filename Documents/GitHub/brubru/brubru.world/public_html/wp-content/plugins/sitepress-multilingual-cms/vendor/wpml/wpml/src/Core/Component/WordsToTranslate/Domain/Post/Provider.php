<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post;

use WPML\Core\Component\WordsToTranslate\Domain\Post\Query\PostQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\ProviderInterface;
use WPML\Core\Component\WordsToTranslate\Domain\TranslatableDTO;
use WPML\PHP\Exception\InvalidItemIdException;
use WPML\PHP\Exception\RuntimeException;

class Provider implements ProviderInterface{
  const TYPE = 'post';

  /** @var PostContentLoader */
  private $postContentLoader;

  /** @var ?PostTermsLoader */
  private $postTermsLoader;

  /** @var PostQueryInterface */
  private $postQuery;


  public function __construct(
    PostQueryInterface $postQuery,
    PostContentLoader $postContentLoader,
    PostTermsLoader $postTermsLoader = null // Use null to ignore terms completely.
  ) {
    $this->postQuery = $postQuery;
    $this->postContentLoader = $postContentLoader;
    $this->postTermsLoader = $postTermsLoader;
  }


  /**
   * @param int $id
   * @param string $type
   * @param string[] $langs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Post|false
   *
   * @throws RuntimeException
   * @throws InvalidItemIdException
   */
  public function getByIdAndTypeForLangs( $id, $type, $langs, $freshTranslation = false ) {
    if ( $type !== self::TYPE ) {
      return false;
    }

    $post = $this->postQuery->getById( $id );

    $this->postContentLoader->loadWordsToTranslateForLangs( $post, $langs, $freshTranslation );

    $this->postTermsLoader &&
      $this->postTermsLoader->loadWordsToTranslateForLangs( $post, $langs );

    return $post;
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

    $this->postContentLoader->getJobQuery()->useThisContentForItem( $id, $content );
  }


}
