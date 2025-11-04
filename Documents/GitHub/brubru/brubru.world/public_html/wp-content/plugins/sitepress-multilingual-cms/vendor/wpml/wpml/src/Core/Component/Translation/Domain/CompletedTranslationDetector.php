<?php

namespace WPML\Core\Component\Translation\Domain;

use WPML\Core\Component\Translation\Domain\PreviousState\PreviousStateQueryInterface;
use WPML\Core\SharedKernel\Component\Translation\Domain\TranslationStatus;


class CompletedTranslationDetector {

  /** @var PreviousStateQueryInterface */
  private $previousStateQuery;


  public function __construct( PreviousStateQueryInterface $previousStateQuery ) {
    $this->previousStateQuery = $previousStateQuery;
  }


  /**
   * Determines if a translation is considered completed.
   *
   * We consider a translation complete when its status is marked as completed and it doesn't need an update.
   * However, we also treat it as completed if the current status is in progress, but it was marked as
   * completed before being sent for translation.
   *
   * @param int      $status The current translation status
   * @param bool     $needsUpdate Whether the translation needs update
   * @param int      $translationId The translation ID
   * @param int|null $translatedElementId The translated element ID (optional)
   *
   * @return bool True if the translation is considered completed, false otherwise
   */
  public function isTranslationCompleted(
    $status,
    $needsUpdate,
    $translationId,
    $translatedElementId = null
  ) {
    $isCompletedTranslationWhichDoesNotNeedUpdate =
      $status === TranslationStatus::COMPLETE && ! $needsUpdate;

    if ( $isCompletedTranslationWhichDoesNotNeedUpdate ) {
      return true;
    }

    /**
     * We want to treat as completed also those jobs which are currently in-progress,
     * but used to be completed and then a user resent them.
     * However, those jobs could not be "needs update". We count only purely "completed" once.
     *
     * Therefore, we have to check if they're in progress at the beginning. Then, we must check if they have
     * translated element. This is the strongest indicator that they used to be completed. A completed translation
     * may not even have a corresponding record in `wp_icl_translation_status` table ( for example when a user used
     * connecting posts feature! ).
     *
     * When translated element exists, we finally have to check whether a translation was "needs update" before.
     * In such a case, a translation must have the existing previous state. It is a very important check. No matter
     * if a translation was resent from TM Dashboard or from the post list ( by clicking the icon ), the previous state
     * always exists and contains the "needs update" flag. We can't tell the same about just Completed translations.
     * The previous state is created for them only if they're resent from TM Dashboard, but not from the post list.
     * Therefore, if there is no previous state, we can tell that a translation could not be "needs update".
     */
    $inProgressStatuses = [
      TranslationStatus::IN_PROGRESS,
      TranslationStatus::WAITING_FOR_TRANSLATOR
    ];
    if (
      in_array( $status, $inProgressStatuses, true ) &&
      $translatedElementId
    ) {
      $previousState = $this->previousStateQuery->getByTranslationId( $translationId );
      if (
        ! $previousState ||
        ( $previousState->getStatus()->get() === TranslationStatus::COMPLETE && ! $previousState->getNeedsUpdate() )
      ) {
        return true;
      }
    }

    return false;
  }


}
