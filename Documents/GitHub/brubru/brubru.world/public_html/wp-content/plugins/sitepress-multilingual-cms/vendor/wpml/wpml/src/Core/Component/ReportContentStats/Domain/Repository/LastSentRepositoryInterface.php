<?php

namespace WPML\Core\Component\ReportContentStats\Domain\Repository;

interface LastSentRepositoryInterface {


  /** @return int|null */
  public function get();


  /** @return void */
  public function update( int $lastSent );


}
