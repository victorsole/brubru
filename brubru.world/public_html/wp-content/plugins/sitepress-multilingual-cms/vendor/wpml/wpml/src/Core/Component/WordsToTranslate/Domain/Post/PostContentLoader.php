<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post;

use WPML\Core\Component\WordsToTranslate\Domain\Calculator\WordsToTranslate;
use WPML\Core\Component\WordsToTranslate\Domain\LastTranslationFactory;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Query\JobQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Query\TranslationQueryInterface;

class PostContentLoader {

  /** @var WordsToTranslate */
  private $wordsToTranslate;

  /** @var Store */
  private $store;

  /** @var TranslationQueryInterface */
  private $translationQuery;

  /** @var JobQueryInterface */
  private $jobQuery;

  /** @var LastTranslationFactory */
  private $lastTranslationFactory;


  public function __construct(
    WordsToTranslate $wordsToTranslate,
    Store $store,
    TranslationQueryInterface $translationQuery,
    JobQueryInterface $jobQuery,
    LastTranslationFactory $lastTranslationFactory
  ) {
    $this->wordsToTranslate = $wordsToTranslate;
    $this->store = $store;
    $this->translationQuery = $translationQuery;
    $this->jobQuery = $jobQuery;
    $this->lastTranslationFactory = $lastTranslationFactory;
  }


  /**
   * @param Post $post
   * @param string[] $langs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return void
   */
  public function loadWordsToTranslateForLangs( Post $post, $langs, $freshTranslation = false ) {
    if ( ! $freshTranslation ) {
      $missingTranslations = $this->store->loadLastTranslations( $post, $langs );
      if ( empty( $missingTranslations ) ) {
        return;
      }
    }

    // Some languages are missing.
    foreach ( $langs as $lang ) {
      $job = $this->jobQuery->getContentToTranslateForLang( $post, $lang );
      $post->setContent( $job->getContent() );

      $lastTranslation = $this->lastTranslationFactory->createForItem( $post, $lang );

      if ( $freshTranslation ) {
        $lastTranslation->setOriginalContent( '' );
      } else {
        $lastTranslationContent = $lastTranslation->getOriginalContent();
        if ( $lastTranslationContent === null ) {
          // Load last translation content for the missing languages.
          $lastTranslationContent =
          $this->translationQuery->getLastTranslatedOriginalContentForPost(
            $post,
            $lang,
            $job->getTranslatableFields()
          );
          $lastTranslation->setOriginalContent( $lastTranslationContent );
        }
      }

      $this->wordsToTranslate->forLastTranslation( $lastTranslation, $post );
      $post->addLastTranslation( $lastTranslation );
    }
  }


  /** @return JobQueryInterface */
  public function getJobQuery() {
    return $this->jobQuery;
  }


}
