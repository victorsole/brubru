<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Job;

use WPML\Core\Component\WordsToTranslate\Domain\Job\Query\JobQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\Job\Query\TranslationEngineQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\ProviderInterface;
use WPML\PHP\Exception\InvalidArgumentException;
use WPML\PHP\Exception\RuntimeException;

class Provider {

  /** @var JobQueryInterface */
  private $jobQuery;

  /** @var TranslationEngineQueryInterface */
  private $translationEngineQuery;

  /** @var ProviderInterface[] */
  private $providers = [];


  /**
   * Provider constructor.
   *
   * @param JobQueryInterface $jobQuery
   * @param TranslationEngineQueryInterface $translationEngineQuery
   * @param ProviderInterface[] $providers
   */
  public function __construct(
    $jobQuery,
    $translationEngineQuery,
    $providers
  ) {
    $this->jobQuery = $jobQuery;
    $this->translationEngineQuery = $translationEngineQuery;
    $this->providers = $providers;
  }


  /**
   * @param int $id
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return JobDTO
   *
   * @throws InvalidArgumentException
   * @throws RuntimeException
   */
  public function getById( $id, $freshTranslation = false ) {
    if ( ! $freshTranslation ) {
      $wordsToTranslate = $this->jobQuery->getWordsToTranslate( $id );

      if ( $wordsToTranslate !== null ) {
        $automaticTranslationCosts = $this->jobQuery->getAutomaticTranslationCosts( $id );

        if ( $automaticTranslationCosts !== null ) {
          // Words to translate and automatic translation costs are already calculated.
          // Return a JobDTO directly.
          return new JobDTO(
            $id,
            $wordsToTranslate,
            $automaticTranslationCosts
          );
        }
      }
    }

    // Fresh translation or no words to translate calculated yet.
    $job = $this->getWithItemById( $id, $freshTranslation );

    return new JobDTO(
      $job->getId(),
      $job->getWordsToTranslate(),
      $job->getAutomaticTranslationCosts(),
      $job->getPreviousAteJobIds()
    );
  }


  /**
   * @param int $id
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Job
   *
   * @throws InvalidArgumentException
   * @throws RuntimeException
   */
  public function getWithItemById( $id, $freshTranslation = false ) {
    $sourceLang = $this->jobQuery->getSourceLang( $id );
    $targetLang = $this->jobQuery->getTargetLang( $id );
    $isAutomatic = $this->jobQuery->isAutomatic( $id );
    $previousAteJobIds = $freshTranslation
      ? []
      : $this->jobQuery->getPreviousAteJobIds( $id );

    $jobItemId = $this->jobQuery->getJobItemId( $id );
    $jobItemType = $this->jobQuery->getJobItemType( $id );

    $item = false;
    $content = $this->jobQuery->getContent( $id );

    foreach ( $this->providers as $provider ) {
      $provider->useThisContentForItem( $jobItemId, $jobItemType, $content );
      if ( $item = $provider->getByIdAndTypeForLangs( $jobItemId, $jobItemType, [ $targetLang ], $freshTranslation ) ) {
        break;
      }
    }

    if ( ! $item ) {
      throw new InvalidArgumentException(
        sprintf(
          'Item with id %d and type %s not found',
          $jobItemId,
          $jobItemType
        )
      );
    }

    return new Job(
      $id,
      $sourceLang,
      $targetLang,
      $item,
      $isAutomatic,
      $previousAteJobIds,
      $this->translationEngineQuery->getCostsPerWordForLang( $targetLang )
    );
  }


}
