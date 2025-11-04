<?php

namespace WPML\Core\Component\Translation\Domain\PreviousState;

use WPML\PHP\Exception\InvalidItemIdException;

interface PreviousStateRepositoryInterface {


  /**
   * @param int                $translationId
   * @param PreviousState|null $previousState
   *
   * @return void
   * @throws InvalidItemIdException
   */
  public function update( int $translationId, PreviousState $previousState = null );


  /**
   * Resets translation status to 0
   *
   * @param int $translationId
   *
   * @return void
   * @throws InvalidItemIdException
   */
  public function resetStatus( int $translationId );


  /**
   * Restores translation status from previous state
   *
   * @param int           $translationId
   * @param PreviousState $previousState
   *
   * @return void
   * @throws InvalidItemIdException
   */
  public function restoreState( int $translationId, PreviousState $previousState );


}
