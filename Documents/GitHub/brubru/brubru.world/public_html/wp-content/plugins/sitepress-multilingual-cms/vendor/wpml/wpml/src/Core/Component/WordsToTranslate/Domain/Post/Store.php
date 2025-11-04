<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post;

class Store {

  /** @var StoreRepositoryInterface */
  private $repository;


  public function __construct(
    StoreRepositoryInterface $repository
  ) {
    $this->repository = $repository;
  }


  /**
   * @return void
   */
  public function save( Post $post ) {
    $this->repository->save( $post );
  }


  /**
   * Loads all the requested languages ($langs) for the given post and returns
   * an array of missing languages.
   *
   * @param Post $post
   * @param string[] $langs
   *
   * @return string[]
   */
  public function loadLastTranslations( Post $post, $langs ) {
    $missingLangs = [];
    $stored = $this->repository->get( $post->getId() );

    if ( ! $stored ) {
      return $langs;
    }

    if ( $stored->getLastEdit() !== $post->getLastEdit() ) {
      // The stored data is outdated.
      return $langs;
    }

    $lastTranslations = $stored->getLastTranslations();
    $missingLangs = [];

    foreach ( $langs as $lang ) {
      if ( ! isset( $lastTranslations[ $lang ] ) ) {
        // Language not stored.
        $missingLangs[] = $lang;
        continue;
      }

      $post->addLastTranslation( $lastTranslations[ $lang ] );
    }

    return $missingLangs;
  }


}
