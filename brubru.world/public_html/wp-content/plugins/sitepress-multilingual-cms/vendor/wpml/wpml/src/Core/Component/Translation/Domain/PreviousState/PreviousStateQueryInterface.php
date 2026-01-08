<?php

namespace WPML\Core\Component\Translation\Domain\PreviousState;

interface PreviousStateQueryInterface {


  /**
   * Get previous state by job ID
   *
   * @param int $jobId
   *
   * @return PreviousState|null
   */
  public function getByJobId( int $jobId );


  /**
   * Get previous state by RID
   *
   * @param int $rid
   *
   * @return PreviousState|null
   */
  public function getByRID( int $rid );


  /**
   * Get previous state by translation ID
   *
   * @param int $translationId
   *
   * @return PreviousState|null
   */
  public function getByTranslationId( int $translationId );


}
