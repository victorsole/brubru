<?php

namespace WPML\Infrastructure\WordPress\Component\Translation\Domain\PreviousState;

use WPML\Core\Component\Translation\Domain\PreviousState\DataCompressInterface;
use WPML\Core\Component\Translation\Domain\PreviousState\PreviousState;
use WPML\Core\Component\Translation\Domain\PreviousState\PreviousStateRepositoryInterface;
use WPML\Core\Port\Persistence\DatabaseWriteInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\Core\SharedKernel\Component\Translation\Domain\TranslationStatus;
use WPML\PHP\Exception\InvalidItemIdException;

class PreviousStateRepository implements PreviousStateRepositoryInterface {

  /** @var DatabaseWriteInterface */
  private $dbWriter;

  /** @var DataCompressInterface */
  private $dataCompress;


  public function __construct( DatabaseWriteInterface $dbWriter, DataCompressInterface $dataCompress ) {
    $this->dbWriter     = $dbWriter;
    $this->dataCompress = $dataCompress;
  }


  /**
   * @param int                $translationId
   * @param PreviousState|null $previousState
   *
   * @return void
   * @throws InvalidItemIdException
   */
  public function update( int $translationId, PreviousState $previousState = null ) {
    $data = $previousState ? $this->dataCompress->compress( $previousState->toArray() ) : null;

    try {
      $updatedItems = $this->dbWriter->update(
        'icl_translation_status',
        [ '_prevstate' => $data ],
        [ 'translation_id' => $translationId ]
      );

      if ( $data !== null && $updatedItems === 0 ) {
        throw $this->getException( $translationId );
      }
    } catch ( DatabaseErrorException $e ) {
      throw $this->getException( $translationId );
    }
  }


  /**
   * Resets translation status to 0
   *
   * @param int $translationId
   *
   * @return void
   * @throws InvalidItemIdException
   */
  public function resetStatus( int $translationId ) {
    try {
      $updatedItems = $this->dbWriter->update(
        'icl_translation_status',
        [ 'status' => TranslationStatus::NOT_TRANSLATED ],
        [ 'translation_id' => $translationId ]
      );

      if ( $updatedItems === 0 ) {
        throw $this->getException( $translationId );
      }
    } catch ( DatabaseErrorException $e ) {
      throw $this->getException( $translationId );
    }
  }


  /**
   * Restores translation status from previous state
   *
   * @param int           $translationId
   * @param PreviousState $previousState
   *
   * @return void
   * @throws InvalidItemIdException
   */
  public function restoreState( int $translationId, PreviousState $previousState ) {
    try {
      $data = $previousState->toArray();

      $updatedItems = $this->dbWriter->update(
        'icl_translation_status',
        $data,
        [ 'translation_id' => $translationId ]
      );

      if ( $updatedItems === 0 ) {
        throw $this->getException( $translationId );
      }
    } catch ( DatabaseErrorException $e ) {
      throw $this->getException( $translationId );
    }
  }


  private function getException( int $translationId ): InvalidItemIdException {
    return new InvalidItemIdException(
      sprintf( 'Translation with ID: %d could not be updated.', $translationId )
    );
  }


}
