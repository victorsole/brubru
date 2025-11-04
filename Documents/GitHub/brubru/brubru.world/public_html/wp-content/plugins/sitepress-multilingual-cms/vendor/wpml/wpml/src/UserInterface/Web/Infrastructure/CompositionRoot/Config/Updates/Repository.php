<?php

namespace WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config\Updates;

use WPML\Core\Port\Persistence\OptionsInterface;

class Repository {
  const OPTION = 'wpml-updates-log';
  const OPTION_KEY_UPDATES = 'updates';

  const UPDATES_KEY_STATUS = 'status';

  const STATUS_IN_PROGRESS = 1;
  const STATUS_COMPLETED = 2;
  const STATUS_FAILED = 3;

  const STATUS_TRY_ONLY_ONCE_STUCK = 4; // A try-only-once update ran into a timeout.
  const STATUS_TRY_ONLY_ONCE_FAILED = 5;

  /** @var OptionsInterface $options */
  private $options;


  public function __construct( OptionsInterface $options ) {
    $this->options = $options;
  }


  /**
   * @param array<int, Update> $allUpdates
   * @return array<int, Update>
   */
  public function getUpdatesToPerform( $allUpdates ) {
    $log = $this->getLog();

    $updatesToPerform = [];

    foreach ( $allUpdates as $update ) {
      if ( ! $update instanceof Update ) {
        continue;
      }

      $updateLog = $log[ self::OPTION_KEY_UPDATES ][ $update->id() ] ?? null;

      if (
        $updateLog
          && in_array(
            $updateLog[ self::UPDATES_KEY_STATUS ],
            [
              self::STATUS_COMPLETED,
              self::STATUS_IN_PROGRESS,
              self::STATUS_TRY_ONLY_ONCE_STUCK,
              self::STATUS_TRY_ONLY_ONCE_FAILED
            ]
          )
      ) {
        continue;
      }

      $updatesToPerform[ $update->id() ] = $update;
    }

    return $updatesToPerform;
  }


  /**
   * @param Update $update
   * @return void
   */
  public function setUpdateInProgress( $update ) {
    $this->setUpdate( $update, self::STATUS_IN_PROGRESS );
  }


  /**
   * @param Update $update
   * @return void
   */
  public function setUpdateComplete( $update ) {
    $this->setUpdate( $update, self::STATUS_COMPLETED );
  }


  /**
   * @param Update $update
   * @return void
   */
  public function setUpdateFailed( $update ) {
    $this->setUpdate( $update, self::STATUS_FAILED );
  }


  /**
   * @param Update $update
   * @return void
   */
  public function setUpdateTryOnlyOnceStuck( $update ) {
    $this->setUpdate( $update, self::STATUS_TRY_ONLY_ONCE_STUCK );
  }


  /**
   * @param Update $update
   * @return void
   */
  public function setUpdateTryOnlyOnceFailed( $update ) {
    $this->setUpdate( $update, self::STATUS_TRY_ONLY_ONCE_FAILED );
  }


  /**
   * @return array{updates: array<int, array{status: int}>}
   *
   * No need to proof the option structure as it's class internal.
   * @psalm-suppress MoreSpecificReturnType
   * @psalm-suppress LessSpecificReturnStatement
   */
  private function getLog() {
    $option = $this->options->get( self::OPTION, false );
    if (
      ! is_array( $option )
      || array_key_exists( 'updated_to', $option )
      || ! array_key_exists( self::OPTION_KEY_UPDATES, $option )
    ) {
      // Legacy option format detected.
      // Retrun fresh log.
      return $this->freshLog();
    }

    return $option;
  }


  /**
   * @param Update $update
   * @param int $status
   * @return void
   */
  private function setUpdate( $update, $status ) {
    $validStatuses = [
      self::STATUS_COMPLETED,
      self::STATUS_FAILED,
      self::STATUS_IN_PROGRESS
    ];

    if ( ! in_array( $status, $validStatuses ) ) {
      return;
    }

    $log = $this->options->get( self::OPTION, [] );
    $log = is_array( $log ) ? $log : [];
    $log[ self::OPTION_KEY_UPDATES ] = $log[ self::OPTION_KEY_UPDATES ] ?? [];

    $log[ self::OPTION_KEY_UPDATES ][ $update->id() ] = [
      self::UPDATES_KEY_STATUS => $status
    ];

    $this->options->save( self::OPTION, $log, true );
  }


  /**
   * @return array{updates: array<int, array{status: int}>}
   */
  private function freshLog() {
    $freshLog = [
      self::OPTION_KEY_UPDATES => [],
    ];

    $this->options->save(
      self::OPTION,
      $freshLog,
      true
    );

    return $freshLog;
  }


}
