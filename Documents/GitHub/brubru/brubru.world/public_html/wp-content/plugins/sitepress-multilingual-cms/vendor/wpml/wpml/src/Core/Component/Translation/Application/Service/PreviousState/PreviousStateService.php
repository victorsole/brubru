<?php

namespace WPML\Core\Component\Translation\Application\Service\PreviousState;

use WPML\Core\Component\Translation\Domain\PreviousState\PreviousState;
use WPML\Core\Component\Translation\Domain\PreviousState\PreviousStateQueryInterface;
use WPML\Core\Component\Translation\Domain\PreviousState\PreviousStateRepositoryInterface;
use WPML\Core\SharedKernel\Component\Translation\Domain\TranslationStatus;
use WPML\PHP\Exception\InvalidItemIdException;


/**
 * @phpstan-type PreviousStateData array{
 *   status: int,
 *   translator_id: int,
 *   needs_update: bool,
 *   md5: string,
 *   translation_service: string,
 *   timestamp: string,
 *   links_fixed: bool
 * }
 */
class PreviousStateService {

  /** @var PreviousStateQueryInterface */
  private $previousStateQuery;

  /** @var PreviousStateRepositoryInterface */
  private $previousStateRepository;


  public function __construct(
    PreviousStateQueryInterface $previousStateQuery,
    PreviousStateRepositoryInterface $previousStateRepository
  ) {
    $this->previousStateQuery      = $previousStateQuery;
    $this->previousStateRepository = $previousStateRepository;
  }


  /**
   * Reverts translation status to its previous state
   *
   * @param int $translationId
   *
   * @return void
   * @throws InvalidItemIdException
   */
  public function revertToPreviousState( int $translationId ) {
    $previousState = $this->previousStateQuery->getByTranslationId( $translationId );

    if ( $previousState ) {
      $this->previousStateRepository->restoreState( $translationId, $previousState );
    } else {
      $this->previousStateRepository->resetStatus( $translationId );
    }

    $this->previousStateRepository->update( $translationId, null );
  }


  /**
   * Gets previous state data for a translation
   *
   * @param int $translationId
   *
   * @return PreviousStateData|null
   */
  public function get( int $translationId ) {
    $previousState = $this->previousStateQuery->getByTranslationId( $translationId );

    if ( ! $previousState ) {
      return null;
    }

    return [
      'status'              => $previousState->getStatus()->get(),
      'translator_id'       => $previousState->getTranslatorId(),
      'needs_update'        => $previousState->getNeedsUpdate(),
      'md5'                 => $previousState->getMd5(),
      'translation_service' => $previousState->getTranslationService(),
      'timestamp'           => $previousState->getTimestamp(),
      'links_fixed'         => $previousState->getLinksFixed()
    ];
  }


  /**
   * Gets previous state data for a translation
   *
   * @param int $rid
   *
   * @return PreviousStateData|null
   */
  public function getByRid( int $rid ) {
    $previousState = $this->previousStateQuery->getByRID( $rid );

    if ( ! $previousState ) {
      return null;
    }

    return [
      'status'              => $previousState->getStatus()->get(),
      'translator_id'       => $previousState->getTranslatorId(),
      'needs_update'        => $previousState->getNeedsUpdate(),
      'md5'                 => $previousState->getMd5(),
      'translation_service' => $previousState->getTranslationService(),
      'timestamp'           => $previousState->getTimestamp(),
      'links_fixed'         => $previousState->getLinksFixed()
    ];
  }


  /**
   * Updates previous state data for a translation
   *
   * @param int $translationId
   * @param array{
   *   status?: int|string,
   *   translator_id?: int,
   *   needs_update?: bool,
   *   md5?: string,
   *   translation_service?: string,
   *   timestamp?: string,
   *   links_fixed?: bool
   * }          $data
   *
   * @return bool
   */
  public function update( int $translationId, array $data ): bool {
    try {
      if (
        ! isset( $data['status'] ) ||
        ! in_array( (int) $data['status'], TranslationStatus::getAll(), true )
      ) {
        return false;
      }

      $mergedData = $this->mergeWithDefaultData( $data );
      $status     = new TranslationStatus( $mergedData['status'] );

      $previousState = new PreviousState(
        $status,
        $mergedData['translator_id'],
        $mergedData['needs_update'],
        $mergedData['md5'],
        $mergedData['translation_service'],
        $mergedData['timestamp'],
        $mergedData['links_fixed']
      );

      $this->previousStateRepository->update( $translationId, $previousState );

      return true;
    } catch ( InvalidItemIdException $e ) {
      return false;
    }
  }


  /**
   * Merges provided data with default values
   *
   * @param array{
   *   status: int|string,
   *   translator_id?: int,
   *   needs_update?: bool,
   *   md5?: string,
   *   translation_service?: string,
   *   timestamp?: string,
   *   links_fixed?: bool
   * } $data
   *
   * @return array{
   *   status: int,
   *   translator_id: int,
   *   needs_update: bool,
   *   md5: string,
   *   translation_service: string,
   *   timestamp: string,
   *   links_fixed: bool
   * }
   */
  private function mergeWithDefaultData( array $data ): array {
    $defaultData = [
      'translator_id'       => 0,
      'needs_update'        => false,
      'md5'                 => '',
      'translation_service' => 'local',
      'timestamp'           => '0',
      'links_fixed'         => false
    ];

    $data           = array_merge( $defaultData, $data );
    $data['status'] = (int) $data['status'];

    return $data;
  }


}
