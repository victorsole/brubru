<?php

namespace WPML\Core\Component\Translation\Application\Service;

use WPML\Core\Component\Translation\Application\Query\TranslationQueryInterface;
use WPML\Core\Component\Translation\Domain\CompletedTranslationDetector;


class CompletedTranslationService {

  /** @var CompletedTranslationDetector */
  private $completedTranslationDetector;

  /** @var TranslationQueryInterface */
  private $translationsQuery;


  public function __construct(
    CompletedTranslationDetector $completedTranslationDetector,
    TranslationQueryInterface $translationsQuery
  ) {
    $this->completedTranslationDetector = $completedTranslationDetector;
    $this->translationsQuery            = $translationsQuery;
  }


  public function hasJobBeenCompletedBeforeResending( int $jobId ): bool {
    $translation = $this->translationsQuery->getOneByJobId( $jobId );
    if ( ! $translation ) {
      return false;
    }

    return $this->completedTranslationDetector->isTranslationCompleted(
      $translation->getStatus()->get(),
      $translation->needsUpdate(),
      $translation->getId(),
      $translation->getTranslatedElementId()
    );
  }


  /**
   * Determines if a translation is considered completed.
   *
   * @param int      $status The current translation status
   * @param bool     $needsUpdate Whether the translation needs update
   * @param int      $translationId The translation ID
   * @param int|null $translatedElementId The translated element ID (optional)
   *
   * @return bool True if the translation is considered completed, false otherwise
   */
  public function isTranslationCompleted( $status, $needsUpdate, $translationId, $translatedElementId = null ) {
    return $this->completedTranslationDetector->isTranslationCompleted(
      $status,
      $needsUpdate,
      $translationId,
      $translatedElementId
    );
  }


}
